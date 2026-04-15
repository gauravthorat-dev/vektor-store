from pose_check import is_valid_pose

image_path = "static/images/user.png"  # your test image

valid, message = is_valid_pose(image_path)

print(message)