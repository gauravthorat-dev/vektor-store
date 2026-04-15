import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose

def overlay_clothing(person_path, cloth_path, output_path):
    # Load images
    person = cv2.imread(person_path)
    cloth = cv2.imread(cloth_path, cv2.IMREAD_UNCHANGED)

    if person is None or cloth is None:
        return False

    person_rgb = cv2.cvtColor(person, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(static_image_mode=True) as pose:
        results = pose.process(person_rgb)

        if not results.pose_landmarks:
            return False

        landmarks = results.pose_landmarks.landmark

        # 🔥 Get shoulders & hips
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_hip = landmarks[23]
        right_hip = landmarks[24]

        h, w, _ = person.shape

        # Convert to pixel
        x1 = int(left_shoulder.x * w)
        y1 = int(left_shoulder.y * h)

        x2 = int(right_shoulder.x * w)
        y2 = int(right_shoulder.y * h)

        hx1 = int(left_hip.x * w)
        hy1 = int(left_hip.y * h)

        hx2 = int(right_hip.x * w)
        hy2 = int(right_hip.y * h)

        # 🔥 AUTO BODY BOUNDING BOX (MAIN LOGIC)
        top_y = min(y1, y2)
        bottom_y = max(hy1, hy2)

        left_x = min(x1, x2)
        right_x = max(x1, x2)

        # 🔥 Add padding (important for natural fit)
        padding_x = int((right_x - left_x) * 0.2)
        padding_y = int((bottom_y - top_y) * 0.1)

        left_x = max(0, left_x - padding_x)
        right_x = min(w, right_x + padding_x)
        top_y = max(0, top_y - padding_y)

        # Width & height
        width = right_x - left_x
        height = bottom_y - top_y

        if width <= 0 or height <= 0:
            return False

        # Resize cloth
        cloth_resized = cv2.resize(cloth, (width, height))

        # 🔥 Smooth edges (better blending)
        cloth_resized = cv2.GaussianBlur(cloth_resized, (3, 3), 0)

        ch, cw, _ = cloth_resized.shape

        # Position (AUTO)
        x_offset = left_x
        y_offset = top_y

        # 🔥 ALPHA BLENDING
        for i in range(ch):
            for j in range(cw):

                if (y_offset + i >= person.shape[0]) or (x_offset + j >= person.shape[1]):
                    continue

                if cloth_resized.shape[2] == 4:
                    alpha = cloth_resized[i][j][3] / 255.0

                    for c in range(3):
                        person[y_offset + i][x_offset + j][c] = (
                            alpha * cloth_resized[i][j][c] +
                            (1 - alpha) * person[y_offset + i][x_offset + j][c]
                        )
                else:
                    person[y_offset + i][x_offset + j] = cloth_resized[i][j]

    # Save result
    cv2.imwrite(output_path, person)
    return True