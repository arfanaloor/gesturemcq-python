import sys
import sqlite3
import hashlib
import json
import cv2
import mediapipe as mp
import numpy as np
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox,
    QStackedWidget, QListWidget, QListWidgetItem, QLineEdit, QFormLayout, QDialog, QComboBox,
    QTextEdit, QGridLayout, QRadioButton, QButtonGroup, QSpinBox, QScrollArea, QFrame ,QTabWidget
)
from PyQt5.QtGui import QFont, QIcon, QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

# Database Setup
def initialize_database():
    conn = sqlite3.connect('gestura.db')
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        FOREIGN KEY (teacher_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )
    ''')

    conn.commit()
    return conn

def get_db_connection():
    return sqlite3.connect('gestura.db')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Video processing thread class
class VideoThread(QThread):
    update_frame = pyqtSignal(QImage)
    gesture_detected = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.cap = None
        self.gesture_cooldown = False
        self.last_gesture_time = 0
        self.cooldown_duration = 2  # seconds
    
    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(0)
        
        with mp_hands.Hands(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5) as hands:
            
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Flip the frame horizontally for a later selfie-view display
                frame = cv2.flip(frame, 1)
                
                # Convert the BGR image to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Process the frame with MediaPipe Hands
                results = hands.process(rgb_frame)
                
                # Draw hand landmarks on the frame
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(
                            frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        
                        # Check if we can detect a gesture now
                        current_time = time.time()
                        if not self.gesture_cooldown or current_time - self.last_gesture_time > self.cooldown_duration:
                            # Get gesture
                            gesture = self.detect_gesture(hand_landmarks)
                            if gesture is not None:
                                self.gesture_detected.emit(gesture)
                                self.gesture_cooldown = True
                                self.last_gesture_time = current_time
                
                # Add help text
                cv2.putText(frame, "Gestures: 1 finger (A), 2 fingers (B), 3 fingers (C), 4 fingers (D)", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Convert to Qt format
                h, w, ch = frame.shape
                qt_image = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
                
                # Emit signal
                self.update_frame.emit(qt_image.rgbSwapped())
                
                # Sleep to reduce CPU usage
                self.msleep(30)
    
    def detect_gesture(self, hand_landmarks):
        # Count extended fingers
        extended_fingers = 0
        
        # Get finger tip and pip (middle joint) landmarks
        tips = [hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP]]
        
        pips = [hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_IP],
                hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_PIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_PIP],
                hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_PIP]]
        
        # Get wrist landmark
        wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
        
        # Check each finger (simplified for demo - just checking if tip is above pip on y-axis)
        # For the thumb, check if it's to the side (x-axis)
        for i in range(5):
            if i == 0:  # Thumb
                if tips[i].x < pips[i].x:  # For right hand
                    extended_fingers += 1
            else:  # Other fingers
                if tips[i].y < pips[i].y:
                    extended_fingers += 1
        
        # Map to answer choices (1-4 fingers = options A-D)
        if 1 <= extended_fingers <= 4:
            return extended_fingers - 1  # Return 0 for A, 1 for B, etc.
        else:
            return None  # No recognized gesture
    
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setWindowIcon(QIcon("icon.png"))
        self.resize(300, 200)
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        
        self.username_input = QLineEdit(self)
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)

        self.role_combobox = QComboBox(self)
        self.role_combobox.addItem("Student")
        self.role_combobox.addItem("Teacher")
        form_layout.addRow("Role:", self.role_combobox)
        
        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Login", self)
        self.login_button.clicked.connect(self.login)
        buttons_layout.addWidget(self.login_button)

        self.register_button = QPushButton("Register", self)
        self.register_button.clicked.connect(self.register)
        buttons_layout.addWidget(self.register_button)
        
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def login(self):
        username = self.username_input.text()
        password = hash_password(self.password_input.text())
        role = self.role_combobox.currentText().lower()

        if not username or not password:
            QMessageBox.warning(self, "Login Failed", "Please enter both username and password")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? AND password = ? AND role = ?", 
                       (username, password, role))
        user = cursor.fetchone()
        conn.close()

        if user:
            self.parent().user_id = user[0]
            self.parent().user_role = role
            self.parent().username = username
            self.accept()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username, password, or role")

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        role = self.role_combobox.currentText().lower()

        if not username or not password:
            QMessageBox.warning(self, "Registration Failed", "Username and password are required")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, hash_password(password), role))
            conn.commit()
            QMessageBox.information(self, "Registration Successful", "You can now log in with your credentials")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Registration Failed", "Username already exists")
        finally:
            conn.close()

class CreateQuizDialog(QDialog):
    def __init__(self, teacher_id, parent=None):
        super().__init__(parent)
        self.teacher_id = teacher_id
        self.questions = []
        
        self.setWindowTitle("Create Quiz")
        self.setWindowIcon(QIcon("icon.png"))
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        self.quiz_title = QLineEdit()
        form_layout.addRow("Quiz Title:", self.quiz_title)
        layout.addLayout(form_layout)
        
        # Question count selection
        self.question_count_layout = QHBoxLayout()
        self.question_count_label = QLabel("Number of Questions:")
        self.question_count = QSpinBox()
        self.question_count.setMinimum(1)
        self.question_count.setMaximum(20)
        self.question_count.setValue(5)
        self.question_count_layout.addWidget(self.question_count_label)
        self.question_count_layout.addWidget(self.question_count)
        layout.addLayout(self.question_count_layout)
        
        self.generate_button = QPushButton("Generate Question Forms")
        self.generate_button.clicked.connect(self.generate_question_forms)
        layout.addWidget(self.generate_button)
        
        # Scroll area for questions
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.questions_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)
        
        self.save_button = QPushButton("Save Quiz")
        self.save_button.clicked.connect(self.save_quiz)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)
        
        self.setLayout(layout)
    
    def generate_question_forms(self):
        # Clear previous forms
        for i in reversed(range(self.questions_layout.count())):
            self.questions_layout.itemAt(i).widget().setParent(None)
        
        num_questions = self.question_count.value()
        
        for i in range(num_questions):
            question_group = QWidget()
            question_layout = QVBoxLayout(question_group)
            
            question_label = QLabel(f"Question {i+1}")
            question_label.setFont(QFont("Arial", 10, QFont.Bold))
            question_layout.addWidget(question_label)
            
            question_text = QLineEdit()
            question_text.setPlaceholderText("Enter question text")
            question_layout.addWidget(question_text)
            
            option_layout = QGridLayout()
            options = []
            
            # Create radio button group for correct answer
            radio_group = QButtonGroup(question_group)
            
            for j in range(4):
                radio = QRadioButton(f"Option {j+1}")
                radio.setChecked(j == 0)  # Default to first option being correct
                radio_group.addButton(radio, j)
                option_layout.addWidget(radio, j, 0)
                
                option_text = QLineEdit()
                option_text.setPlaceholderText(f"Enter option {j+1}")
                option_layout.addWidget(option_text, j, 1)
                options.append(option_text)
            
            question_layout.addLayout(option_layout)
            self.questions_layout.addWidget(question_group)
            
            # Store references to form elements
            question_data = {
                'text': question_text,
                'options': options,
                'correct_answer': radio_group
            }
            
            if i < len(self.questions):
                self.questions[i] = question_data
            else:
                self.questions.append(question_data)
        
        self.save_button.setEnabled(True)
    
    def save_quiz(self):
        title = self.quiz_title.text()
        
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a quiz title")
            return
        
        # Validate all questions have content
        for i, q in enumerate(self.questions):
            if not q['text'].text():
                QMessageBox.warning(self, "Error", f"Question {i+1} is missing text")
                return
            
            for j, opt in enumerate(q['options']):
                if not opt.text():
                    QMessageBox.warning(self, "Error", f"Question {i+1}, Option {j+1} is missing text")
                    return
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert quiz
            cursor.execute("INSERT INTO quizzes (teacher_id, title) VALUES (?, ?)",
                          (self.teacher_id, title))
            quiz_id = cursor.lastrowid
            
            # Insert questions
            for i, q in enumerate(self.questions):
                question_text = q['text'].text()
                options = [opt.text() for opt in q['options']]
                correct_answer = q['correct_answer'].checkedId()
                
                cursor.execute(
                    "INSERT INTO questions (quiz_id, question_text, options, correct_answer) VALUES (?, ?, ?, ?)",
                    (quiz_id, question_text, json.dumps(options), correct_answer)
                )
            
            conn.commit()
            QMessageBox.information(self, "Success", "Quiz created successfully")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save quiz: {str(e)}")
        finally:
            conn.close()

class GestureQuizDialog(QDialog):
    def __init__(self, student_id, quiz_id, quiz_title, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.quiz_id = quiz_id
        self.quiz_title = quiz_title
        self.questions = []
        self.current_question_idx = 0
        self.user_answers = {}
        
        # Get questions
        self.load_questions()
        
        # Set up UI
        self.setWindowTitle(f"Gesture Quiz: {quiz_title}")
        self.resize(1000, 700)
        
        main_layout = QHBoxLayout()
        
        # Left side - quiz content
        self.quiz_layout = QVBoxLayout()
        
        # Quiz title
        title_label = QLabel(quiz_title)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.quiz_layout.addWidget(title_label)
        
        # Question display
        self.question_frame = QFrame()
        self.question_frame.setFrameShape(QFrame.StyledPanel)
        self.question_frame.setMinimumHeight(300)
        self.question_layout = QVBoxLayout(self.question_frame)
        
        # Question text
        self.question_label = QLabel()
        self.question_label.setFont(QFont("Arial", 12))
        self.question_label.setWordWrap(True)
        self.question_layout.addWidget(self.question_label)
        
        # Options
        self.option_buttons = []
        self.option_layout = QVBoxLayout()
        for i in range(4):
            option_btn = QRadioButton()
            option_btn.setFont(QFont("Arial", 11))
            self.option_buttons.append(option_btn)
            self.option_layout.addWidget(option_btn)
        
        self.question_layout.addLayout(self.option_layout)
        self.quiz_layout.addWidget(self.question_frame)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_question)
        nav_layout.addWidget(self.prev_button)
        
        self.question_counter = QLabel("Question 1 of X")
        nav_layout.addWidget(self.question_counter)
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_question)
        nav_layout.addWidget(self.next_button)
        
        self.submit_button = QPushButton("Submit Quiz")
        self.submit_button.clicked.connect(self.submit_quiz)
        nav_layout.addWidget(self.submit_button)
        
        self.quiz_layout.addLayout(nav_layout)
        
        # Gesture instructions
        gesture_info = QLabel(
            "Use hand gestures to select answers:\n"
            "• 1 finger (index) = Option A\n"
            "• 2 fingers (index + middle) = Option B\n"
            "• 3 fingers = Option C\n"
            "• 4 fingers = Option D"
        )
        gesture_info.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        self.quiz_layout.addWidget(gesture_info)
        
        main_layout.addLayout(self.quiz_layout, 2)
        
        # Right side - camera view
        camera_layout = QVBoxLayout()
        
        camera_label = QLabel("Hand Gesture Camera")
        camera_label.setFont(QFont("Arial", 14, QFont.Bold))
        camera_layout.addWidget(camera_label)
        
        self.camera_view = QLabel()
        self.camera_view.setMinimumSize(400, 300)
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setStyleSheet("border: 2px solid #888; background-color: #000;")
        camera_layout.addWidget(self.camera_view)
        
        self.gesture_status = QLabel("Waiting for gesture...")
        self.gesture_status.setAlignment(Qt.AlignCenter)
        self.gesture_status.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        camera_layout.addWidget(self.gesture_status)
        
        main_layout.addLayout(camera_layout, 1)
        
        self.setLayout(main_layout)
        
        # Initialize video capture thread
        self.video_thread = VideoThread()
        self.video_thread.update_frame.connect(self.update_camera_view)
        self.video_thread.gesture_detected.connect(self.handle_gesture)
        self.video_thread.start()
        
        # Display first question
        self.display_question(0)
        
    def load_questions(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, question_text, options, correct_answer FROM questions WHERE quiz_id = ?", (self.quiz_id,))
        self.questions = cursor.fetchall()
        
        conn.close()
    
    def display_question(self, idx):
        if not self.questions or idx < 0 or idx >= len(self.questions):
            return
        
        q_id, question_text, options_json, correct_answer = self.questions[idx]
        options = json.loads(options_json)
        
        self.question_label.setText(f"Question {idx+1}: {question_text}")
        
        for i, opt in enumerate(self.option_buttons):
            if i < len(options):
                opt.setText(f"{chr(65+i)}. {options[i]}")
                opt.setVisible(True)
                
                # Check if user already answered this question
                if q_id in self.user_answers and self.user_answers[q_id] == i:
                    opt.setChecked(True)
                else:
                    opt.setChecked(False)
            else:
                opt.setVisible(False)
        
        self.question_counter.setText(f"Question {idx+1} of {len(self.questions)}")
        
        # Update navigation buttons
        self.prev_button.setEnabled(idx > 0)
        self.next_button.setEnabled(idx < len(self.questions) - 1)
        self.submit_button.setEnabled(True)
        
        # Update current question index
        self.current_question_idx = idx
    
    def next_question(self):
        # Save current answer if selected
        self.save_current_answer()
        
        # Move to next question
        if self.current_question_idx < len(self.questions) - 1:
            self.display_question(self.current_question_idx + 1)
    
    def previous_question(self):
        # Save current answer if selected
        self.save_current_answer()
        
        # Move to previous question
        if self.current_question_idx > 0:
            self.display_question(self.current_question_idx - 1)
    
    def save_current_answer(self):
        if not self.questions:
            return
        
        q_id = self.questions[self.current_question_idx][0]
        
        # Find selected option
        for i, opt in enumerate(self.option_buttons):
            if opt.isChecked():
                self.user_answers[q_id] = i
                break
    
    def submit_quiz(self):
        # Save final answer
        self.save_current_answer()
        
        # Check if all questions are answered
        if len(self.user_answers) < len(self.questions):
            reply = QMessageBox.question(self, "Incomplete Quiz", 
                                         f"You've only answered {len(self.user_answers)} of {len(self.questions)} questions. "
                                         "Do you want to submit anyway?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # Calculate score
        score = 0
        for q_id, _, _, correct_answer in self.questions:
            if q_id in self.user_answers and self.user_answers[q_id] == correct_answer:
                score += 1
        
        # Save result to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO results (student_id, quiz_id, score, total_questions) VALUES (?, ?, ?, ?)",
            (self.student_id, self.quiz_id, score, len(self.questions))
        )
        
        conn.commit()
        conn.close()
        
        # Stop video thread
        self.video_thread.stop()
        
        # Show result
        QMessageBox.information(self, "Quiz Result", 
                                f"Your score: {score}/{len(self.questions)} ({score/len(self.questions)*100:.1f}%)")
        
        self.accept()
    
    def update_camera_view(self, image):
        self.camera_view.setPixmap(QPixmap.fromImage(image).scaled(
            self.camera_view.width(), self.camera_view.height(), 
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def handle_gesture(self, gesture_id):
        # Map gesture to an option (0-3)
        option_texts = ["A (Index finger)", "B (Two fingers)", "C (Three fingers)", "D (Four fingers)"]
        
        if 0 <= gesture_id <= 3:
            self.gesture_status.setText(f"Detected: Option {option_texts[gesture_id]}")
            self.gesture_status.setStyleSheet("font-size: 14px; font-weight: bold; color: green; padding: 5px;")
            
            # Select the corresponding radio button
            self.option_buttons[gesture_id].setChecked(True)
            
            # Save the answer
            self.save_current_answer()
            
            # Optional: Auto-advance to next question after a short delay
            QTimer.singleShot(1500, lambda: self.auto_advance())
    
    def auto_advance(self):
        # Auto-advance to next question if there is one
        if self.current_question_idx < len(self.questions) - 1:
            self.next_question()
        else:
            # Flash the submit button if on last question
            self.submit_button.setStyleSheet("background-color: #ff9900;")
            QTimer.singleShot(1000, lambda: self.submit_button.setStyleSheet(""))
    
    def closeEvent(self, event):
        # Stop video thread when dialog closes
        self.video_thread.stop()
        event.accept()

class QuizWidget(QWidget):
    def __init__(self, user_id, user_role, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Header
        self.header_label = QLabel("Available Quizzes")
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.header_label)
        
        # Quiz list
        self.quiz_list = QListWidget()
        self.quiz_list.itemDoubleClicked.connect(self.on_quiz_selected)
        layout.addWidget(self.quiz_list)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh Quizzes")
        self.refresh_button.clicked.connect(self.load_quizzes)
        button_layout.addWidget(self.refresh_button)
        
        # Create quiz button (teachers only)
        if self.user_role == "teacher":
            self.create_quiz_button = QPushButton("Create New Quiz")
            self.create_quiz_button.clicked.connect(self.create_quiz)
            button_layout.addWidget(self.create_quiz_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.load_quizzes()
    
    def load_quizzes(self):
        self.quiz_list.clear()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if self.user_role == "teacher":
            # Teachers see only their own quizzes
            cursor.execute("""
                SELECT q.id, q.title, COUNT(qu.id) 
                FROM quizzes q 
                LEFT JOIN questions qu ON q.id = qu.quiz_id 
                WHERE q.teacher_id = ? 
                GROUP BY q.id
            """, (self.user_id,))
        else:
            # Students see all quizzes
            cursor.execute("""
                SELECT q.id, q.title, COUNT(qu.id) 
                FROM quizzes q 
                LEFT JOIN questions qu ON q.id = qu.quiz_id 
                GROUP BY q.id
            """)
        
        quizzes = cursor.fetchall()
        conn.close()
        
        for quiz_id, title, question_count in quizzes:
            item = QListWidgetItem(f"{title} ({question_count} questions)")
            item.setData(Qt.UserRole, quiz_id)
            item.setData(Qt.UserRole + 1, title)
            self.quiz_list.addItem(item)
    
    def on_quiz_selected(self, item):
        quiz_id = item.data(Qt.UserRole)
        quiz_title = item.data(Qt.UserRole + 1)
        
        if self.user_role == "teacher":
            # Teachers can view quiz details
            self.show_quiz_details(quiz_id)
        else:
            # Students can take the quiz with gestures
            reply = QMessageBox.question(self, "Quiz Mode", 
                                       "Choose quiz mode:\n\nYes: Use gesture recognition\nNo: Standard mode",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.take_gesture_quiz(quiz_id, quiz_title)
            else:
                self.take_quiz(quiz_id)
    
    def create_quiz(self):
        dialog = CreateQuizDialog(self.user_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_quizzes()
    
    def take_gesture_quiz(self, quiz_id, quiz_title):
        # Check if student has already taken this quiz
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM results WHERE student_id = ? AND quiz_id = ?", 
                      (self.user_id, quiz_id))
        existing_result = cursor.fetchone()
        conn.close()
        
        if existing_result:
            reply = QMessageBox.question(self, "Retake Quiz", 
                                         "You have already taken this quiz. Would you like to take it again?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        dialog = GestureQuizDialog(self.user_id, quiz_id, quiz_title, self)
        dialog.exec_()
        self.load_quizzes()
    
    def take_quiz(self, quiz_id):
        # Standard quiz-taking function (without gestures)
        QMessageBox.information(self, "Standard Quiz", 
                               "Standard quiz mode is not implemented in this demo")
    
    def show_quiz_details(self, quiz_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get quiz details
        cursor.execute("SELECT title FROM quizzes WHERE id = ?", (quiz_id,))
        quiz_title = cursor.fetchone()[0]
        
        # Get questions
        cursor.execute("SELECT question_text, options, correct_answer FROM questions WHERE quiz_id = ?", (quiz_id,))
        questions = cursor.fetchall()
        
        # Get results
        cursor.execute("""
            SELECT u.username, r.score, r.total_questions 
            FROM results r 
            JOIN users u ON r.student_id = u.id 
            WHERE r.quiz_id = ? 
            ORDER BY r.score DESC
        """, (quiz_id,))
        results = cursor.fetchall()
        
        conn.close()
        
        # Display quiz details
        details = QDialog(self)
        details.setWindowTitle(f"Quiz Details: {quiz_title}")
        details.resize(600, 400)
        
        layout = QVBoxLayout()
        
        # Quiz title
        title_label = QLabel(quiz_title)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title_label)
        
        # Questions section
        q_label = QLabel("Questions:")
        q_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(q_label)
        
        for i, (question, options_json, correct) in enumerate(questions):
            options = json.loads(options_json)
            q_frame = QFrame()
            q_frame.setFrameShape(QFrame.StyledPanel)
            q_layout = QVBoxLayout(q_frame)
            
            q_text = QLabel(f"Q{i+1}: {question}")
            q_text.setWordWrap(True)
            q_layout.addWidget(q_text)
            
            for j, opt in enumerate(options):
                opt_text = QLabel(f"  {chr(65+j)}. {opt}")
                if j == correct:
                    opt_text.setStyleSheet("color: green; font-weight: bold;")
                q_layout.addWidget(opt_text)
            
            layout.addWidget(q_frame)
        
        # Results section
        if results:
            r_label = QLabel("Student Results:")
            r_label.setFont(QFont("Arial", 12, QFont.Bold))
            layout.addWidget(r_label)
            
            results_text = QTextEdit()
            results_text.setReadOnly(True)
            
            results_str = ""
            for username, score, total in results:
                percentage = (score / total) * 100
                results_str += f"{username}: {score}/{total} ({percentage:.1f}%)\n"
            
            results_text.setText(results_str)
            layout.addWidget(results_text)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(details.accept)
        layout.addWidget(close_button)
        
        details.setLayout(layout)
        details.exec_()

class ResultsWidget(QWidget):
    def __init__(self, user_id, user_role, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_role = user_role
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Header
        if self.user_role == "teacher":
            self.header_label = QLabel("Student Results")
        else:
            self.header_label = QLabel("My Quiz Results")
        self.header_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.header_label)
        
        # Results display
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh Results")
        self.refresh_button.clicked.connect(self.load_results)
        layout.addWidget(self.refresh_button)
        
        self.setLayout(layout)
        self.load_results()
    
    def load_results(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if self.user_role == "teacher":
            # Teachers see results for their quizzes
            cursor.execute("""
                SELECT q.title, u.username, r.score, r.total_questions, r.id
                FROM results r
                JOIN quizzes q ON r.quiz_id = q.id
                JOIN users u ON r.student_id = u.id
                WHERE q.teacher_id = ?
                ORDER BY q.title, r.score DESC
            """, (self.user_id,))
        else:
            # Students see their own results
            cursor.execute("""
                SELECT q.title, r.score, r.total_questions, r.id
                FROM results r
                JOIN quizzes q ON r.quiz_id = q.id
                WHERE r.student_id = ?
                ORDER BY r.id DESC
            """, (self.user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            self.results_text.setText("No results found.")
            return
        
        if self.user_role == "teacher":
            # Format results for teachers
            text = ""
            current_quiz = None
            
            for quiz_title, username, score, total, _ in results:
                if quiz_title != current_quiz:
                    if current_quiz:
                        text += "\n\n"
                    text += f"Quiz: {quiz_title}\n"
                    text += "-" * 40 + "\n"
                    current_quiz = quiz_title
                
                percentage = (score / total) * 100
                text += f"{username}: {score}/{total} ({percentage:.1f}%)\n"
        else:
            # Format results for students
            text = ""
            
            for quiz_title, score, total, _ in results:
                percentage = (score / total) * 100
                text += f"Quiz: {quiz_title}\n"
                text += f"Score: {score}/{total} ({percentage:.1f}%)\n"
                
                # Add performance assessment
                if percentage >= 90:
                    text += "Performance: Excellent!\n"
                elif percentage >= 80:
                    text += "Performance: Very Good\n"
                elif percentage >= 70:
                    text += "Performance: Good\n"
                elif percentage >= 60:
                    text += "Performance: Satisfactory\n"
                else:
                    text += "Performance: Needs Improvement\n"
                
                text += "-" * 40 + "\n\n"
        
        self.results_text.setText(text)

class HelpWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Gestura - Hand Gesture Quiz System")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Instructions text
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Using Gestura</h2>
        
        <h3>For Students:</h3>
        <ul>
            <li><b>Taking Quizzes:</b> Double-click on a quiz in the Quiz tab to begin.</li>
            <li><b>Gesture Control:</b> When taking a quiz in gesture mode, hold up fingers to select answers:
                <ul>
                    <li>1 finger (index) = Option A</li>
                    <li>2 fingers (index + middle) = Option B</li>
                    <li>3 fingers = Option C</li>
                    <li>4 fingers = Option D</li>
                </ul>
            </li>
            <li><b>View Results:</b> Check your performance in the Results tab.</li>
        </ul>
        
        <h3>For Teachers:</h3>
        <ul>
            <li><b>Create Quizzes:</b> Click "Create New Quiz" in the Quiz tab.</li>
            <li><b>View Quiz Details:</b> Double-click on your quiz to see questions and student results.</li>
            <li><b>Monitor Performance:</b> See all student results in the Results tab.</li>
        </ul>
        
        <h3>Hand Gesture Tips:</h3>
        <ul>
            <li>Ensure good lighting for better gesture recognition.</li>
            <li>Hold your hand clearly in the camera's view.</li>
            <li>Keep fingers straight and clearly separated.</li>
            <li>Hold the gesture for 1-2 seconds to register.</li>
            <li>After a gesture is recognized, there's a 2-second cooldown.</li>
        </ul>
        """)
        layout.addWidget(help_text)
        
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestura")
        self.setWindowIcon(QIcon("icon.png"))
        self.resize(800, 600)
        self.user_id = None
        self.user_role = None
        self.username = None
        
        # Initialize database
        initialize_database()
        
        # Show login dialog
        self.show_login()
    
    def show_login(self):
        dialog = LoginDialog(self)
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            self.setup_main_ui()
        else:
            # Exit if login is cancelled
            sys.exit()
    
    def setup_main_ui(self):
        # Update window title to show logged in user
        self.setWindowTitle(f"Gestura - Logged in as {self.username} ({self.user_role})")
        
        # Create central widget with tabs
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Create quiz tab
        self.quiz_tab = QuizWidget(self.user_id, self.user_role)
        self.tabs.addTab(self.quiz_tab, "Quizzes")
        
        # Create results tab
        self.results_tab = ResultsWidget(self.user_id, self.user_role)
        self.tabs.addTab(self.results_tab, "Results")
        
        # Create help tab
        self.help_tab = HelpWidget()
        self.tabs.addTab(self.help_tab, "Help")
        
        main_layout.addWidget(self.tabs)
        
        # Create logout button
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        main_layout.addWidget(self.logout_button)
    
    def logout(self):
        # Reset user info
        self.user_id = None
        self.user_role = None
        self.username = None
        
        # Clear central widget
        self.central_widget.setParent(None)
        self.central_widget = None
        
        # Show login dialog again
        self.show_login()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
