"""
socketio_events.py
──────────────────
Register all Socket.IO events here.
Import and call register_events(socketio) from your app.py.

In app.py add:
──────────────
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    from socketio_events import register_events
    register_events(socketio)

    if __name__ == "__main__":
        socketio.run(app, debug=True)
"""

from flask import session, request
from flask_socketio import join_room, leave_room, emit
from services.dispatch_service import accept_order, reject_order, expire_dispatch
from models.user_model import User


def register_events(socketio):

    # ── CONNECT ──────────────────────────────────────────────
    @socketio.on("connect")
    def on_connect():
        user_id = session.get("user_id")
        role    = session.get("user_role")   # store role in session on login
        if not user_id:
            return False  # reject anonymous connections

        if role == "delivery_boy":
            join_room(f"boy_{user_id}")
            emit("connected", {"msg": f"Joined delivery room boy_{user_id}"})

        elif role in ("admin", "superadmin"):
            join_room("admin_room")
            emit("connected", {"msg": "Joined admin room"})

    # ── DISCONNECT ───────────────────────────────────────────
    @socketio.on("disconnect")
    def on_disconnect():
        user_id = session.get("user_id")
        role    = session.get("user_role")
        if user_id and role == "delivery_boy":
            leave_room(f"boy_{user_id}")

    # ── DELIVERY BOY: ACCEPT ORDER ───────────────────────────
    @socketio.on("accept_order")
    def on_accept(data):
        """
        Client emits: { order_id: 123 }
        """
        user_id  = session.get("user_id")
        order_id = data.get("order_id")
        if not user_id or not order_id:
            return

        result = accept_order(order_id, user_id)
        emit("accept_result", result)   # back to this boy only

    # ── DELIVERY BOY: REJECT ORDER ───────────────────────────
    @socketio.on("reject_order")
    def on_reject(data):
        """
        Client emits: { order_id: 123 }
        """
        user_id  = session.get("user_id")
        order_id = data.get("order_id")
        if not user_id or not order_id:
            return

        reject_order(order_id, user_id)
        emit("reject_result", {"ok": True})

    # ── DELIVERY BOY: TIMEOUT EXPIRED (client-side timer done) ──
    @socketio.on("order_timeout")
    def on_timeout(data):
        """
        Client emits after countdown hits 0: { order_id: 123 }
        """
        user_id  = session.get("user_id")
        order_id = data.get("order_id")
        if user_id and order_id:
            expire_dispatch(order_id, user_id)

    # ── DELIVERY BOY: HEARTBEAT (mark as online) ─────────────
    @socketio.on("heartbeat")
    def on_heartbeat():
        """Client pings every 30s to stay marked as active."""
        from database.db import db
        from models.dispatch_model import DeliveryBoyStats
        user_id = session.get("user_id")
        if user_id:
            from datetime import datetime
            stats = DeliveryBoyStats.query.filter_by(delivery_boy_id=user_id).first()
            if not stats:
                stats = DeliveryBoyStats(delivery_boy_id=user_id)
                db.session.add(stats)
            stats.last_active_at = datetime.utcnow()
            db.session.commit()

    # ── ADMIN: MANUAL BROADCAST ──────────────────────────────
    @socketio.on("admin_broadcast_order")
    def on_admin_broadcast(data):
        """Admin manually re-broadcasts a failed dispatch."""
        from services.dispatch_service import broadcast_order
        order_id = data.get("order_id")
        if order_id:
            broadcast_order(order_id)