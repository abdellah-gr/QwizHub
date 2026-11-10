# QwizHub

QwizHub is a web-based quiz platform that allows users to create, manage, share, and play interactive multiple-choice quizzes.

## Features

### User Accounts

Users can create an account, log in, and log out securely. Passwords are stored as hashes rather than plain text.

From the account page, users can also change their username or password. Accounts can be permanently deleted after confirming the user's password and typing a confirmation message. Deleting an account also removes its related quizzes, questions, choices, and ranking data.

### Quiz Creation

Logged-in users can create their own quizzes by providing:

* A title
* An optional description
* A category
* Public or private visibility
* Shuffle mode

QwizHub includes several quiz categories such as Programming, Mathematics, Science, History, Geography, Languages, Sports, Entertainment, and General Knowledge.

After creating a quiz, users can add multiple questions to it. Each question contains between 2 and 4 choices, with one choice marked as the correct answer.

### Quiz Management

Quiz creators have full control over their quizzes.

They can edit quiz information such as its title, description, category, visibility, and shuffle mode.

Questions and choices can be added, edited, deleted, and manually reordered.

The application prevents certain invalid actions, such as creating a question with fewer than 2 choices or without a correct answer. It also prevents the correct choice from being deleted directly and ensures that each question has at least 2 choices and only one correct answer.

Whenever an important part of a quiz is modified, its latest-update timestamp is updated and its existing ranking is cleared when necessary so that old scores do not remain after the quiz itself has changed.

### Playing Quizzes

Users can play quizzes one question at a time.

When an answer is submitted, QwizHub checks whether it is correct, updates the player's score, and moves to the next question. At the end of the quiz, the final score is displayed.

### Shuffle Mode

Quiz creators can enable **Shuffle Mode**.

When enabled, the order of both the questions and their choices is randomized each time a new attempt begins. The randomized order is kept during the attempt, meaning refreshing a question does not continuously reshuffle its choices.

When Shuffle Mode is disabled, questions and choices appear in the order selected by the quiz creator.

### Explore

Public quizzes can be discovered from the **Explore** page.

The page displays quizzes created by the QwizHub community and allows users to choose and play quizzes made by other users.

Private quizzes are not displayed on the Explore page.

### Rankings

Each quiz has its own leaderboard where players can save their scores.

Rankings are ordered primarily by score, allowing users to compare their results with other players.

A user can improve an existing leaderboard entry by achieving a higher score. Lower or equal scores cannot replace their current high score.

Quiz creators cannot submit their own results to the ranking of their quizzes.

## Technologies Used

QwizHub was built using:

* **Python**: Back-end application logic
* **Flask**: Routing, form handling, sessions, and server-side functionality
* **SQLite**: Persistent storage for users, quizzes, questions, choices, and rankings
* **sqlite3** (Python standard library): Database access through a small wrapper in `database.py`
* **Jinja**: Dynamic generation of HTML pages using data from Flask
* **HTML**: Structure of the web pages
* **Bootstrap**: Main user-interface design and responsive components
* **CSS**: Additional interface styling
* **Werkzeug**: Secure password hashing and verification
* **Flask-Session**: Server-side user session management

## Project Structure

The application uses a relational SQLite database to connect the different parts of QwizHub.

Users can own multiple quizzes. Each quiz can contain multiple questions, and each question can contain 2-4 choices. Rankings connect users to the quizzes they have played and store their best scores.

The Flask application handles authentication, quiz creation and editing, quiz attempts, scoring, rankings, and account management. Helper functions are used for repeated operations such as deleting related database records, updating quiz timestamps, clearing rankings, and restricting pages to authenticated users.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create the database:
   ```
   sqlite3 qwizhub.db < schema.sql
   ```
3. Run the app:
   ```
   flask run
   ```
4. Open the address printed in the terminal (usually `http://127.0.0.1:5000`).

## Development

QwizHub was built over about 25 days between August and September 2026. It was my first major web project. During development, I worked on designing the database structure, implementing the quiz-playing system, handling user authentication, maintaining the order of questions and choices, creating the ranking system, implementing shuffle mode, and building the quiz management interface.

The app originally used a different SQL helper library. I replaced it with Python's standard `sqlite3` module through a small wrapper (`database.py`), which was written with AI assistance (Claude, by Anthropic). The HTML templates and Bootstrap styling were made by me, but were later polished with AI assistance (Gemini, by Google) on top of my original UI. The Flask application logic, database design, and routes are my own work.

## Known Limitations

This project is no longer in active development. The issues below are known and will not be fixed, so please don't deploy it publicly as is.

### Security
- **No ownership checks:** any logged-in user can edit or delete another user's quiz, question, or choice by changing the ID in the URL.
- **No CSRF protection** on forms.
- **Private quizzes aren't fully private:** they're hidden from the Explore page, but anyone with the direct play or ranking URL can access them.
- **Answers can be tampered with:** the correct/incorrect value is sent from the browser, so a player could edit the form and always submit the correct answer.
- **No rate limiting** on login attempts.
- **No password rules or username validation** (very short passwords are accepted).
- **No `SECRET_KEY`** configured.

### Bugs and robustness
- Requesting a nonexistent quiz, question, or choice ID causes a server error instead of a 404 page.
- Changing a username to one that's already taken causes an unhandled error.
- Scores are stored in the session and not tied to a specific quiz, so a result can be saved to the wrong quiz's ranking.
- Opening a results page without playing first raises an error.
- Editing a correct choice and unchecking "correct" can leave a question with no correct answer.
- Reordering can fail if `order_num` values contain gaps or duplicates.
- Some edit forms don't trim whitespace, so blank-looking text can be saved.

### Quality
- No automated tests.
- No input length limits.
- Reorder logic is duplicated between questions and choices.

## Project Status

No longer in active development. Treat it as a learning project and reference, not production software.
