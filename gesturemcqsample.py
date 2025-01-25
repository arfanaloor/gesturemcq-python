import cv2
import mediapipe as mp
import pyautogui

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

# OpenCV Video Capture
cap = cv2.VideoCapture(0)

# Predefined questions and options
questions = [
    {"question": "What is the capital of France?", "options": ["Paris", "Berlin", "Madrid", "Rome"], "answer": 1},
    {"question": "Which planet is known as the Red Planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"],
     "answer": 2},
    {"question": "Who wrote 'Hamlet'?", "options": ["Shakespeare", "Dickens", "Austen", "Hemingway"], "answer": 1},
]

current_question = 0
selected_option = None
score = 0


def display_question():
    global current_question
    question_data = questions[current_question]
    print("\nQuestion:", question_data["question"])
    for i, option in enumerate(question_data["options"], start=1):
        print(f"{i}. {option}")


# Define gesture-to-action mapping
def interpret_gesture(landmarks):
    index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
    middle_tip = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
    ring_tip = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP]
    pinky_tip = landmarks[mp_hands.HandLandmark.PINKY_TIP]
    thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]

    # Determine the number of fingers raised
    fingers = [
        thumb_tip.x < landmarks[mp_hands.HandLandmark.THUMB_IP].x,
        index_tip.y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP].y,
        middle_tip.y < landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y,
        ring_tip.y < landmarks[mp_hands.HandLandmark.RING_FINGER_PIP].y,
        pinky_tip.y < landmarks[mp_hands.HandLandmark.PINKY_PIP].y
    ]

    finger_count = sum(fingers)

    if finger_count == 1:
        return 1
    elif finger_count == 2:
        return 2
    elif finger_count == 3:
        return 3
    elif finger_count == 4:
        return 4
    elif finger_count == 5:
        return "Submit"
    return None


print("Starting gesture-based MCQ solver... Press 'q' to exit.")
display_question()

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Flip the frame horizontally for natural interaction
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw hand landmarks on the frame
                mp_drawing.draw_landmarks(
                    frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Interpret gestures
                gesture = interpret_gesture(hand_landmarks.landmark)

                if gesture in [1, 2, 3, 4]:
                    selected_option = gesture
                    print(
                        f"Option {selected_option} selected: {questions[current_question]['options'][selected_option - 1]}")

                if gesture == "Submit" and selected_option is not None:  # Submit answer when 5 fingers are raised
                    if selected_option == questions[current_question]["answer"]:
                        print("Correct answer!")
                        score += 1
                    else:
                        print("Wrong answer.")

                    current_question += 1
                    selected_option = None
                    if current_question < len(questions):
                        display_question()
                    else:
                        print(f"All questions completed! Your final score is {score}/{len(questions)}.")
                        cap.release()
                        cv2.destroyAllWindows()
                        hands.close()
                        exit()

        # Display the frame
        cv2.imshow('Gesture-Based MCQ Solver', frame)

        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    # Release resources
    cap.release()
    cv2.destroyAllWindows()
    hands.close()
    print(f"Exited successfully. Your final score is {score}/{len(questions)}.")
