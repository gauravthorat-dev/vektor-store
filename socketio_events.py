"""Socket.IO event registration."""

from flask import request, session
from flask_socketio import emit, join_room, leave_room

from services.dispatch_service import (
    accept_order_atomic,
    emit_stats_update,
    expire_dispatch,
    reject_order,
    set_delivery_boy_presence,
    touch_delivery_boy_heartbeat,
)


def register_events(socketio):
    """Register all Socket.IO event handlers."""

    def _join_delivery_rooms(user_id: int):
        """Join global and personal delivery rooms."""
        join_room("delivery_boys")
        join_room(f"boy_{user_id}")
        emit(
            "room_joined",
            {
                "room": "delivery_boys",
                "uid": user_id,
                "namespace": getattr(request, "namespace", "/"),
            },
        )

    @socketio.on("connect")
    def on_connect():
        """Handle socket connect and role-based room join."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        admin_id = session.get("admin_id")

        if user_id and role == "delivery_boy":
            _join_delivery_rooms(int(user_id))
            set_delivery_boy_presence(user_id, True)
            emit("connected", {"msg": "Connected as delivery boy"})
            return

        if admin_id or role in ("admin", "superadmin"):
            join_room("admin_room")
            emit("connected", {"msg": "Connected as admin"})
            emit_stats_update()
            return

        return False

    @socketio.on("disconnect")
    def on_disconnect():
        """Handle socket disconnect cleanup."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        if user_id and role == "delivery_boy":
            leave_room(f"boy_{user_id}")
            leave_room("delivery_boys")
            set_delivery_boy_presence(user_id, False)

    @socketio.on("join_delivery_room")
    def on_join_delivery_room():
        """Rejoin delivery rooms on every connect/reconnect."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        if not user_id or role != "delivery_boy":
            return
        _join_delivery_rooms(int(user_id))

    @socketio.on("accept_order")
    def on_accept(data):
        """Attempt atomic first-come accept for shipped order."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        order_id = (data or {}).get("order_id")
        if not user_id or role != "delivery_boy" or not order_id:
            emit("accept_result", {"ok": False, "message": "Invalid request."})
            return

        result = accept_order_atomic(int(order_id), int(user_id))
        emit("accept_result", result)

    @socketio.on("reject_order")
    def on_reject(data):
        """Record rejection from delivery boy."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        order_id = (data or {}).get("order_id")
        if not user_id or role != "delivery_boy" or not order_id:
            emit("reject_result", {"ok": False, "message": "Invalid request."})
            return
        reject_order(int(order_id), int(user_id))
        emit("reject_result", {"ok": True, "message": "Order rejected."})

    @socketio.on("order_timeout")
    def on_timeout(data):
        """Record client-side timeout for telemetry."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        order_id = (data or {}).get("order_id")
        if user_id and role == "delivery_boy" and order_id:
            expire_dispatch(int(order_id), int(user_id))

    @socketio.on("heartbeat")
    def on_heartbeat():
        """Keep delivery boy online via 30s heartbeat."""
        user_id = session.get("user_id")
        role = session.get("user_role")
        if user_id and role == "delivery_boy":
            touch_delivery_boy_heartbeat(int(user_id))
