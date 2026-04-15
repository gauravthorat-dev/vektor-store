import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose

def is_valid_pose(image_path):
    # Load image
    image = cv2.imread(image_path)

    if image is None:
        return False, "Image not found"

    # Convert to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(static_image_mode=True) as pose:
        results = pose.process(image_rgb)

        # If no body detected
        if not results.pose_landmarks:
            return False, "No body detected"

        landmarks = results.pose_landmarks.landmark

        # Get shoulders
        left = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]

        # Check visibility
        if left.visibility > 0.5 and right.visibility > 0.5:
            return True, "Valid pose ✅"
        else:
            return False, "Please upload front-facing image ❌"