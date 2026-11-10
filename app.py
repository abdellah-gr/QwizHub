import random

from database import DB
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session

from werkzeug.security import check_password_hash, generate_password_hash

from helpers import (
    login_required,
    update_quiz_timestamp,
    clear_ranking,
    quiz_modified,
    delete_quiz_data,
    delete_question_data,
    delete_account_data,
)

# Configure application
app = Flask(__name__)


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Configure database
db = DB("qwizhub.db")

# Quiz categories
categories = [
    "Programming",
    "Mathematics",
    "Science",
    "History",
    "Geography",
    "Languages",
    "Sports",
    "Entertainment",
    "General Knowledge",
    "Other",
]


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    # user_id is used to determine the link for "Get Started" button
    return render_template("index.html", user_id=session.get("user_id"))


@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    # Get the user's username
    username = db.execute(
        "SELECT username FROM users WHERE id = ?", session["user_id"]
    )[0]["username"]

    # Get all the user's quizzes
    quizzes = db.execute(
        "SELECT * FROM quizzes WHERE creator_id = ? ORDER BY title", session["user_id"]
    )
    return render_template("home.html", user=username, quizzes=quizzes, source="home")


@app.route("/explore", methods=["GET", "POST"])
@login_required
def explore():
    # Get all the info related to quizzes (quizzes ids, creator name, quiz title, category, visibility, creation date, and latest update)
    quizzes = db.execute(
        """
        SELECT DISTINCT quizzes.id ,username, title, category, visibility, creation_date, updated_at
        FROM users
        INNER JOIN quizzes ON users.id = quizzes.creator_id
        INNER JOIN questions ON quizzes.id = questions.quiz_id
        WHERE visibility = ?
        AND NULLIF(TRIM(text), ?) IS NOT NULL
        ORDER BY title
        """,
        "Public",
        "",
    )

    return render_template("explore.html", quizzes=quizzes, source="explore")


@app.route("/new_quiz", methods=["GET", "POST"])
@login_required
def new_quiz():
    if request.method == "POST":
        # Get quiz title
        title = request.form.get("quiz_title").strip()
        if not title:
            flash("Missing quiz title!", "danger")
            return render_template("new_quiz.html", categories=categories)

        # Get quiz description
        description = request.form.get("quiz_description").strip()

        # Get quiz category
        category = request.form.get("quiz_category")
        if not category:
            flash("Missing quiz category!", "danger")
            return render_template("new_quiz.html", categories=categories)

        # Get quiz visibility
        visibility = request.form.get("quiz_visibility")
        if not visibility:
            flash("Missing quiz visibility!", "danger")
            return render_template("new_quiz.html", categories=categories)

        # Check if shuffle mode is on or off
        shuffle_mode = "On" if request.form.get("shuffle_mode") == "On" else "Off"

        # Insert the created quiz into the quizzes table and get its id (INSERT returns the primary key which is the id in this case)
        quiz_id = db.execute(
            "INSERT INTO quizzes (creator_id, title, description, category, visibility, shuffle_mode) VALUES (?, ?, ?, ?, ?, ?)",
            session["user_id"],
            title,
            description,
            category,
            visibility,
            shuffle_mode,
        )

        # Shows an alert to the user that the quiz was made successfully and redirect the user to add a new questions
        flash("Quiz Created!", "success")
        return redirect(f"/quiz/{quiz_id}/edit/new_question")
    else:
        return render_template("new_quiz.html", categories=categories)


@app.route("/quiz/<int:quiz_id>/edit/new_question", methods=["GET", "POST"])
@login_required
def new_question(quiz_id):
    if request.method == "POST":

        # Get the order of the new question (number of existing questions plus 1)
        order_num = (
            len(db.execute("SELECT * FROM questions WHERE quiz_id = ?", quiz_id)) + 1
        )

        # Get question text
        question_text = request.form.get("question_text").strip()
        if not question_text:
            flash("Missing question text!", "danger")
            return render_template("new_question.html", quiz_id=quiz_id)

        # Initialize a list of dicts for choices where to put their texts, their indexes, and their types
        choices = []

        # Append choices texts and their indexes to the choices list of dicts
        for i in range(4):
            choice_text = request.form.get(f"choice_text_{i + 1}").strip()
            if choice_text:
                choices.append({"text": choice_text, "index": i})

        # Check if the user has typed at least 2 non-blank choices
        if len(choices) < 2:
            flash("Question needs at least two choices!", "danger")
            return render_template("new_question.html", quiz_id=quiz_id)

        # Get correct choice index (type=int handles the case of a missing correct choice, it avoids TypeError and returns None if the user didn't chose a correct answer)
        correct_choice_index = request.form.get("correct_choice_index", type=int)

        # Append choices types to the choices list of dicts
        for order, choice in enumerate(choices):
            choice["order"] = order + 1
            if choice["index"] == correct_choice_index:
                choice["type"] = "Correct"
            else:
                choice["type"] = "Incorrect"

        # Check there is a correct answer
        if not any(choice["type"] == "Correct" for choice in choices):
            flash("Missing correct choice!", "danger")
            return render_template("new_question.html", quiz_id=quiz_id)

        # Add question to the questions table and get the question id
        question_id = db.execute(
            "INSERT INTO questions (quiz_id, text, order_num) VALUES (?, ?, ?)",
            quiz_id,
            question_text,
            order_num,
        )

        # Add choices to the choices table
        for choice in choices:
            db.execute(
                "INSERT INTO choices (question_id, order_num, text, type) VALUES (?, ?, ?, ?)",
                question_id,
                choice["order"],
                choice["text"],
                choice["type"],
            )

        # Update quiz "updated at" timestamp and clear quiz ranking
        quiz_modified(db, quiz_id)

        # Alert the user that the question was added to the quiz successfully
        flash("Question Added!", "success")
        return redirect(f"/quiz/{quiz_id}/edit")
    else:
        return render_template("new_question.html", quiz_id=quiz_id)


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>/new_choice",
    methods=["GET", "POST"],
)
@login_required
def new_choice(quiz_id, question_id):
    # Get all existing choices of the question
    existing_choices = db.execute(
        "SELECT * FROM choices WHERE question_id = ?", question_id
    )

    # Get order of the new choice (Number of existing choices plus 1)
    order_num = len(existing_choices) + 1

    if request.method == "POST":
        # Get new choice text
        choice_text = request.form.get("choice_text").strip()
        if not choice_text:
            flash("Missing choice text!", "danger")
            return render_template(
                "new_choice.html", quiz_id=quiz_id, question_id=question_id
            )

        # Get new choice type (Correct if the user checked the checkbox, else it's Incorrect)
        choice_type = "Correct" if request.form.get("choice_type") else "Incorrect"

        # If the new choice is correct, all the existing choices will become incorrect
        if choice_type == "Correct":
            for choice in existing_choices:
                db.execute(
                    "UPDATE choices SET type = 'Incorrect' WHERE id = ?", choice["id"]
                )

        # Insert the choice into the database
        db.execute(
            "INSERT INTO choices (question_id, order_num, text, type) VALUES (?, ?, ?, ?)",
            question_id,
            order_num,
            choice_text,
            choice_type,
        )

        # Update quiz "updated at" timestamp and clear quiz ranking
        quiz_modified(db, quiz_id)

        # Alert the user that the choice was added successfully
        flash("Choice Added!", "success")
        return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")
    else:
        return render_template(
            "new_choice.html", quiz_id=quiz_id, question_id=question_id
        )


@app.route("/<source>/quiz/<int:quiz_id>/play", methods=["GET", "POST"])
@login_required
def play_quiz(source, quiz_id):
    # Get quiz info
    quiz = db.execute(
        "SELECT title, description, category, shuffle_mode FROM quizzes WHERE id = ?",
        quiz_id,
    )[0]

    # Get number of questions
    num_of_questions = db.execute(
        "SELECT COUNT(*) AS num_of_questions FROM questions WHERE quiz_id = ?", quiz_id
    )[0]["num_of_questions"]

    # Check if the quiz has at least one question or more
    if num_of_questions >= 1:
        quiz_not_empty = True
    else:
        quiz_not_empty = False

    if request.method == "POST":
        # Initialize the score, the question's index, the quiz's questions list, and turn off shuffle mode by default
        session["score"] = 0
        session["question_index"] = 0
        session["shuffle_mode"] = "Off"
        session["questions"] = db.execute(
            "SELECT id, text FROM questions WHERE quiz_id = ? ORDER BY order_num",
            quiz_id,
        )
        # Make sure that the choices order get set after redirecting to the specified route
        session["choices_order_set"] = False
        if quiz["shuffle_mode"] == "On":
            # Shuffle all the questions
            random.shuffle(session["questions"])
            session["shuffle_mode"] = "On"

        return redirect(f"/{source}/quiz/{quiz_id}/play/question")
    else:
        return render_template(
            "play_quiz.html",
            quiz=quiz,
            source=source,
            quiz_id=quiz_id,
            quiz_not_empty=quiz_not_empty,
            shuffle_mode=quiz["shuffle_mode"],
        )


@app.route("/<source>/quiz/<int:quiz_id>/play/question", methods=["GET", "POST"])
@login_required
def question(source, quiz_id):
    # Get quiz title
    quiz_title = db.execute("SELECT title FROM quizzes WHERE id = ?", quiz_id)[0][
        "title"
    ]

    # If the user spammed "Next question" button until going out of questions indexes
    if session["question_index"] >= len(session["questions"]):
        return redirect(f"/{source}/quiz/{quiz_id}/play/results")
    else:
        # Get current question
        current_question = session["questions"][session["question_index"]]

    # Get current question choices
    # If the choices order isn't set yet (avoids shuffling after page refresh)
    if not session["choices_order_set"]:
        session["choices"] = db.execute(
            "SELECT id, text, type FROM choices WHERE question_id = ?",
            current_question["id"],
        )
        # If shuffle mode is on
        if session["shuffle_mode"] == "On":
            random.shuffle(session["choices"])
        # Choices order is set
        session["choices_order_set"] = True

    if request.method == "POST":

        # If the user chooses the correct answer
        if request.form.get("choice") == "Correct":
            session["score"] += 1
        session["question_index"] += 1
        session["choices_order_set"] = False
        # Show final score if there aren't any questions left
        if session["question_index"] >= len(session["questions"]):
            return redirect(f"/{source}/quiz/{quiz_id}/play/results")
        # Next question
        return redirect(f"/{source}/quiz/{quiz_id}/play/question")
    else:
        return render_template(
            "question.html",
            source=source,
            quiz_id=quiz_id,
            quiz_title=quiz_title,
            question_index=session["question_index"] + 1,
            num_of_questions=len(session["questions"]),
            question=current_question,
            choices=session["choices"],
        )


@app.route("/<source>/quiz/<int:quiz_id>/play/results", methods=["GET", "POST"])
@login_required
def result(source, quiz_id):
    # Get all existing user's entries from the quiz ranking
    existing_entries = db.execute(
        """
        SELECT username, score
        FROM rankings
        INNER JOIN users ON rankings.user_id = users.id
        WHERE rankings.quiz_id = ?
        """,
        quiz_id,
    )

    # Get the user's username
    username = db.execute(
        "SELECT username FROM users WHERE id = ?", session["user_id"]
    )[0]["username"]

    # Get quiz title
    quiz_title = db.execute("SELECT title FROM quizzes WHERE id = ?", quiz_id)[0][
        "title"
    ]
    # Get quiz questions
    questions = db.execute("SELECT id, text FROM questions WHERE quiz_id = ?", quiz_id)

    # Get quiz creator id
    creator_id = db.execute("SELECT creator_id FROM quizzes WHERE id = ?", quiz_id)[0][
        "creator_id"
    ]

    if request.method == "POST":
        new_user = True
        for entry in existing_entries:
            # Check if the player already exist in the ranking
            if username == entry["username"]:
                # Update the player's entry
                db.execute(
                    "UPDATE rankings SET score = ?, date = ? WHERE user_id = ? AND quiz_id = ?",
                    session["score"],
                    datetime.now(),
                    session["user_id"],
                    quiz_id,
                )
                new_user = False
                break

        # If it's his first entry, insert the result into the ranking
        if new_user:
            db.execute(
                "INSERT INTO rankings (quiz_id, user_id, score) VALUES (?, ?, ?)",
                quiz_id,
                session["user_id"],
                session["score"],
            )

        # Alert the user that his result was saved successfully
        flash("Result Saved!", "success")
        return redirect(f"/{source}/quiz/{quiz_id}/play")
    else:
        all_conditions_met = True
        # Remove "Save results" button if the player is the quiz creator
        if session["user_id"] == creator_id:
            all_conditions_met = False
        # If the user's score is 0 (null) or less (The user needs to score 1 or more points to be able to save his result)
        elif session["score"] <= 0:
            all_conditions_met = False
        # Remove "Save Result" button if the player has scored less than his high score entry
        else:
            for entry in existing_entries:
                # Check if the player already exist in the ranking
                if username == entry["username"]:
                    if session["score"] <= entry["score"]:
                        all_conditions_met = False
                        break

        # If the player isn't the quiz creator, his score isn't null, it's his first entry, or has got a score higher than his previous entry
        if all_conditions_met:
            show_save_results_button = True
        else:
            show_save_results_button = False

        return render_template(
            "results.html",
            source=source,
            quiz_id=quiz_id,
            quiz_title=quiz_title,
            score=session["score"],
            num_of_questions=len(questions),
            show_save_results_button=show_save_results_button,
        )


@app.route("/<source>/quiz/<int:quiz_id>/ranking", methods=["GET", "POST"])
@login_required
def ranking(source, quiz_id):
    # Get actual user's username (to display his name in bold font)
    username = db.execute(
        "SELECT username FROM users WHERE id = ?", session["user_id"]
    )[0]["username"]

    # Get quiz entries ranking
    ranking = db.execute(
        """
        SELECT username, score, date
        FROM rankings
        INNER JOIN users ON rankings.user_id = users.id
        WHERE rankings.quiz_id = ?
        ORDER BY score DESC, date
        """,
        quiz_id,
    )

    # Get quiz title
    quiz_title = db.execute("SELECT title FROM quizzes WHERE id = ?", quiz_id)[0][
        "title"
    ]

    # Get number of questions
    num_of_questions = db.execute(
        "SELECT COUNT(*) AS num_of_questions FROM questions WHERE quiz_id = ?", quiz_id
    )[0]["num_of_questions"]

    return render_template(
        "ranking.html",
        quiz_title=quiz_title,
        username=username,
        ranking=ranking,
        num_of_questions=num_of_questions,
    )


@app.route("/quiz/<int:quiz_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quiz(quiz_id):
    # Get quiz title and shuffle mode
    quiz_info = db.execute(
        "SELECT title, shuffle_mode FROM quizzes WHERE id = ?", quiz_id
    )[0]

    # Get quiz questions
    questions = db.execute(
        "SELECT * FROM questions WHERE quiz_id = ? ORDER BY order_num", quiz_id
    )
    return render_template(
        "edit_quiz.html", quiz_id=quiz_id, quiz_info=quiz_info, questions=questions
    )


@app.route("/quiz/<int:quiz_id>/edit/info", methods=["GET", "POST"])
@login_required
def edit_quiz_info(quiz_id):
    # Get quiz info
    quiz_info = db.execute("SELECT * FROM quizzes WHERE id = ?", quiz_id)[0]

    if request.method == "POST":

        # Get quiz title
        quiz_title = request.form.get("quiz_title").strip()
        if quiz_title:
            # Update quiz title
            db.execute("UPDATE quizzes SET title = ? WHERE id = ?", quiz_title, quiz_id)

        # Get quiz description
        quiz_description = request.form.get("quiz_description").strip()
        if quiz_description:
            # Update quiz description
            db.execute(
                "UPDATE quizzes SET description = ? WHERE id = ?",
                quiz_description,
                quiz_id,
            )

        # Get quiz category
        quiz_category = request.form.get("quiz_category")
        if quiz_category:
            # Update quiz category
            db.execute(
                "UPDATE quizzes SET category = ? WHERE id = ?", quiz_category, quiz_id
            )

        # Get quiz visibility
        quiz_visibility = request.form.get("quiz_visibility")
        if quiz_visibility:
            # Update quiz visibility
            db.execute(
                "UPDATE quizzes SET visibility = ? WHERE id = ?",
                quiz_visibility,
                quiz_id,
            )

        # Check if shuffle mode is on or off
        shuffle_mode = "On" if request.form.get("shuffle_mode") == "On" else "Off"
        # If the user changed shuffle mode's condition
        if shuffle_mode != quiz_info["shuffle_mode"]:
            # Update shuffle mode's condition
            db.execute(
                "UPDATE quizzes SET shuffle_mode = ? WHERE id = ?",
                shuffle_mode,
                quiz_id,
            )
            clear_ranking(db, quiz_id)

        # Update quiz "updated at" timestamp
        update_quiz_timestamp(db, quiz_id)
        # Alert the user that the quiz info was updated successfully
        flash("Quiz Info Edited!", "success")

        return redirect(f"/quiz/{quiz_id}/edit")
    else:
        return render_template(
            "edit_quiz_info.html",
            quiz_id=quiz_id,
            quiz_title=quiz_info["title"],
            quiz_description=quiz_info["description"],
            quiz_category=quiz_info["category"],
            quiz_visibility=quiz_info["visibility"],
            shuffle_mode=quiz_info["shuffle_mode"],
            categories=categories,
        )


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>", methods=["GET", "POST"]
)
@login_required
def edit_question(quiz_id, question_id):
    # Get shuffle mode
    shuffle_mode = db.execute("SELECT shuffle_mode FROM quizzes WHERE id = ?", quiz_id)[
        0
    ]["shuffle_mode"]

    # Get question text
    question_text = db.execute("SELECT text FROM questions WHERE id = ?", question_id)[
        0
    ]["text"]

    # Get the question choices
    choices = db.execute(
        "SELECT * FROM choices WHERE question_id = ? ORDER BY order_num", question_id
    )

    return render_template(
        "edit_question.html",
        quiz_id=quiz_id,
        question_id=question_id,
        question_text=question_text,
        choices=choices,
        shuffle_mode=shuffle_mode,
    )


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>/text", methods=["GET", "POST"]
)
@login_required
def edit_question_text(quiz_id, question_id):
    # Get question text
    old_question_text = db.execute(
        "SELECT text FROM questions WHERE id = ?", question_id
    )[0]["text"]

    if request.method == "POST":

        # Get new question text
        question_text = request.form.get("question_text")
        if question_text:
            # Update question text
            db.execute(
                "UPDATE questions SET text = ? WHERE id = ?", question_text, question_id
            )
            # Update quiz "updated at" timestamp and clear quiz ranking
            quiz_modified(db, quiz_id)
            # Alert the user that the question text was updated successfully
            flash("Question Edited!", "success")

        return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")

    else:
        return render_template(
            "edit_question_text.html",
            quiz_id=quiz_id,
            question_id=question_id,
            question_text=old_question_text,
        )


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>/order/<direction>",
    methods=["GET", "POST"],
)
@login_required
def edit_question_order(quiz_id, question_id, direction):

    # Get number of questions
    num_of_questions = db.execute(
        "SELECT COUNT(*) AS num_of_questions FROM questions WHERE quiz_id = ?", quiz_id
    )[0]["num_of_questions"]

    # Get the order of the question that the user wants to change its order
    question_order = db.execute(
        "SELECT order_num FROM questions WHERE id = ?", question_id
    )[0]["order_num"]

    if direction == "up":
        if question_order - 1 <= 0:
            flash("Invalid Action!", "danger")
        else:
            # Get the id of the question above the one that the user wants to move up
            question_above_id = db.execute(
                "SELECT id FROM questions WHERE order_num = ? AND quiz_id = ?",
                question_order - 1,
                quiz_id,
            )[0]["id"]

            # Move the question the user wants to move up
            db.execute(
                "UPDATE questions SET order_num = ? WHERE id = ?",
                question_order - 1,
                question_id,
            )

            # Move the question above down
            db.execute(
                "UPDATE questions SET order_num = ? WHERE id = ?",
                question_order,
                question_above_id,
            )

            flash("Questions Order Changed!", "success")
    else:
        if question_order + 1 > num_of_questions:
            flash("Invalid Action!", "danger")
        else:
            # Get the id of the question below the one that the user wants to move down
            question_below_id = db.execute(
                "SELECT id FROM questions WHERE order_num = ? AND quiz_id = ?",
                question_order + 1,
                quiz_id,
            )[0]["id"]

            # Move the question the user wants to move down
            db.execute(
                "UPDATE questions SET order_num = ? WHERE id = ?",
                question_order + 1,
                question_id,
            )

            # Move the question below up
            db.execute(
                "UPDATE questions SET order_num = ? WHERE id = ?",
                question_order,
                question_below_id,
            )
            flash("Questions Order Changed!", "success")

    return redirect(f"/quiz/{quiz_id}/edit")


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>/choice/<int:choice_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_choice(quiz_id, question_id, choice_id):
    # Get choice
    choice = db.execute("SELECT text, type FROM choices WHERE id = ?", choice_id)[0]

    # Get all existing choices of the question except the choice that is being edited
    existing_choices = db.execute(
        "SELECT * FROM choices WHERE question_id = ? AND id != ?",
        question_id,
        choice_id,
    )

    if request.method == "POST":

        choice_text = request.form.get("choice_text")
        if choice_text:
            # Update choice text
            db.execute(
                "UPDATE choices SET text = ? WHERE id = ?", choice_text, choice_id
            )

        # Get choice type (Correct if the user checked the checkbox, else it's Incorrect)
        choice_type = "Correct" if request.form.get("choice_type") else "Incorrect"

        # If the user has edited the choice to be correct, all other choices will become incorrect
        if choice_type == "Correct":
            for choice in existing_choices:
                db.execute(
                    "UPDATE choices SET type = 'Incorrect' WHERE id = ?",
                    choice["id"],
                )

        # Update choice type
        db.execute("UPDATE choices SET type = ? WHERE id = ?", choice_type, choice_id)

        # Update quiz "updated at" timestamp and clear quiz ranking
        quiz_modified(db, quiz_id)
        # Alert the user that the choice was edited successfully
        flash("Choice Edited!", "success")

        return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")
    else:
        return render_template(
            "edit_choice.html",
            quiz_id=quiz_id,
            question_id=question_id,
            choice_id=choice_id,
            choice_text=choice["text"],
            choice_type=choice["type"],
        )


@app.route(
    "/quiz/<int:quiz_id>/edit/question/<int:question_id>/choice/<int:choice_id>/order/<direction>",
    methods=["GET", "POST"],
)
@login_required
def edit_choice_order(quiz_id, question_id, choice_id, direction):

    # Get number of choices
    num_of_choices = db.execute(
        "SELECT COUNT(*) AS num_of_choices FROM choices WHERE question_id = ?",
        question_id,
    )[0]["num_of_choices"]

    # The choice that the user wants to change its order
    choice_order = db.execute("SELECT order_num FROM choices WHERE id = ?", choice_id)[
        0
    ]["order_num"]

    if direction == "up":
        if choice_order - 1 <= 0:
            flash("Invalid Action!", "danger")
        else:
            # Get the id of the choice above the one that the user wants to move up
            choice_above_id = db.execute(
                "SELECT id FROM choices WHERE order_num = ? AND question_id = ?",
                choice_order - 1,
                question_id,
            )[0]["id"]

            # Move the choice the user wants to move up
            db.execute(
                "UPDATE choices SET order_num = ? WHERE id = ?",
                choice_order - 1,
                choice_id,
            )

            # Move the choice above down
            db.execute(
                "UPDATE choices SET order_num = ? WHERE id = ?",
                choice_order,
                choice_above_id,
            )

            flash("Choices Order Changed!", "success")
    else:
        if choice_order + 1 > num_of_choices:
            flash("Invalid Action!", "danger")
        else:
            # Get the id of the choice below the one that the user wants to move down
            choice_below_id = db.execute(
                "SELECT id FROM choices WHERE order_num = ? AND question_id = ?",
                choice_order + 1,
                question_id,
            )[0]["id"]

            # Move the choice the user wants to move down
            db.execute(
                "UPDATE choices SET order_num = ? WHERE id = ?",
                choice_order + 1,
                choice_id,
            )

            # Move the choice below up
            db.execute(
                "UPDATE choices SET order_num = ? WHERE id = ?",
                choice_order,
                choice_below_id,
            )
            flash("Questions Order Changed!", "success")

    return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")


@app.route("/quiz/<int:quiz_id>/delete", methods=["GET", "POST"])
@login_required
def delete_quiz(quiz_id):
    # Get quiz title
    quiz_title = db.execute("SELECT title FROM quizzes WHERE id = ?", quiz_id)[0][
        "title"
    ]

    if request.method == "POST":
        # Delete all quiz data
        delete_quiz_data(db, quiz_id)

        # Tell the user that the quiz was deleted successfully
        flash("Quiz Deleted!", "success")
        return redirect("/home")
    else:
        return render_template(
            "delete_quiz.html", quiz_id=quiz_id, quiz_title=quiz_title
        )


@app.route(
    "/quiz/<int:quiz_id>/delete/question/<int:question_id>", methods=["GET", "POST"]
)
@login_required
def delete_question(quiz_id, question_id):
    # Get question text
    question_text = db.execute("SELECT text FROM questions WHERE id = ?", question_id)[
        0
    ]["text"]

    if request.method == "POST":
        # Get all quiz questions except the one the user wants to delete
        questions = db.execute(
            "SELECT id, order_num FROM questions WHERE id != ? and quiz_id = ?",
            question_id,
            quiz_id,
        )

        # Get deleted question order
        deleted_question_order = db.execute(
            "SELECT order_num FROM questions WHERE id = ?", question_id
        )[0]["order_num"]

        # Delete question data
        delete_question_data(db, question_id)

        # Reorder the remaining questions
        for question in questions:
            if question["order_num"] > deleted_question_order:
                db.execute(
                    "UPDATE questions SET order_num = ? WHERE id = ?",
                    question["order_num"] - 1,
                    question["id"],
                )

        # Update quiz "updated at" timestamp and clear quiz ranking
        quiz_modified(db, quiz_id)

        # Alert the user that the question was deleted successfully
        flash("Question Deleted!", "success")
        return redirect(f"/quiz/{quiz_id}/edit")
    else:
        return render_template(
            "delete_question.html",
            quiz_id=quiz_id,
            question_id=question_id,
            question_text=question_text,
        )


@app.route(
    "/quiz/<int:quiz_id>/delete/question/<int:question_id>/choice/<int:choice_id>",
    methods=["GET", "POST"],
)
@login_required
def delete_choice(quiz_id, question_id, choice_id):
    # Get choice info
    choice_info = db.execute("SELECT * FROM choices WHERE id = ?", choice_id)[0]

    # Get number of choices
    num_of_choices = db.execute(
        "SELECT COUNT(*) AS num_of_choices FROM choices WHERE question_id = ?",
        question_id,
    )[0]["num_of_choices"]

    if request.method == "POST":
        # Get all quiz questions except the one the user wants to delete
        choices = db.execute(
            "SELECT id, order_num FROM choices WHERE id != ? and question_id = ?",
            choice_id,
            question_id,
        )

        # Get deleted question order
        deleted_choice_order = db.execute(
            "SELECT order_num FROM choices WHERE id = ?", choice_id
        )[0]["order_num"]

        # Delete the choice from the database
        db.execute("DELETE FROM choices WHERE id = ?", choice_id)

        # Reorder the remaining questions
        for choice in choices:
            if choice["order_num"] > deleted_choice_order:
                db.execute(
                    "UPDATE choices SET order_num = ? WHERE id = ?",
                    choice["order_num"] - 1,
                    choice["id"],
                )

        # Update quiz "updated at" timestamp and clear quiz ranking
        quiz_modified(db, quiz_id)

        # Alert the user that the choice was removed successfully
        flash("Choice Deleted!", "success")
        return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")
    else:
        # Prevent the user from deleting a correct answer
        if choice_info["type"] == "Correct" or num_of_choices <= 2:
            flash("Invalid Action!", "danger")
            return redirect(f"/quiz/{quiz_id}/edit/question/{question_id}")

        else:
            return render_template(
                "delete_choice.html",
                quiz_id=quiz_id,
                question_id=question_id,
                choice_id=choice_id,
                choice_text=choice_info["text"],
            )


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username!", "danger")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password!", "danger")
            return render_template("login.html")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            flash("Invalid username and/or password!", "danger")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page and alert him that he logged in successfully
        flash("Logged in!", "success")
        return redirect("/home")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()

    # Redirect user to index page
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Check if the username isn't blank
        username = request.form.get("username")
        if not username:
            flash("Missing username!", "danger")
            return render_template("register.html")

        # Check if the password isn't blank
        password = request.form.get("password")
        if not password:
            flash("Missing password!", "danger")
            return render_template("register.html")

        # Check if the password matches the password confirmation
        if password != request.form.get("confirmation"):
            flash("Passwords don't match!", "danger")
            return render_template("register.html")

        # Securely hash the password and add the user to the database,
        # If the username is already taken, raise an error and cancel the registration
        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                username,
                generate_password_hash(password),
            )
        except ValueError:
            flash("Username taken!", "danger")
            return render_template("register.html")

        # Show an alert that the user has successfully registered
        flash("Registered!", "success")

        # Log the user in with his newly registered account
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        session["user_id"] = rows[0]["id"]
        return redirect("/home")

    else:
        return render_template("register.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    # Get user info
    user_info = (
        db.execute(
            "SELECT username, join_date FROM users WHERE id = ?", session["user_id"]
        )
    )[0]

    # Get join_date info (day, month, year, hour, minute, second)
    join_date = datetime.strptime(user_info["join_date"], "%Y-%m-%d %H:%M:%S")

    return render_template(
        "account.html",
        username=user_info["username"],
        date=join_date.strftime("%B %d, %Y"),
    )


@app.route("/change_username", methods=["GET", "POST"])
@login_required
def change_username():
    # Get user's hashed password
    user_hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[
        0
    ]["hash"]

    if request.method == "POST":
        # Get user's new username
        new_username = request.form.get("new_username")
        if not new_username:
            flash("Missing new username!", "danger")
            return render_template("change_username.html")

        # Check if the new username and its confirmation matches
        if new_username != request.form.get("new_username_confirmation"):
            flash("Usernames don't match!", "danger")
            return render_template("change_username.html")

        # Get user's password
        password = request.form.get("password")
        if not password:
            flash("Missing password!", "danger")
            return render_template("change_username.html")

        # Check if the user has typed the correct password
        if not check_password_hash(user_hash, password):
            flash("Incorrect password!", "danger")
            return render_template("change_username.html")

        # Securely hash the new password and update user's password in the database
        db.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            new_username,
            session["user_id"],
        )

        # Returns the user to the homepage and show an alert that password was changed successfully
        flash("Username Changed!", "success")
        return redirect("/account")

    else:
        return render_template("change_username.html")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    # Get user's old hashed password
    user_old_hash = db.execute(
        "SELECT hash FROM users WHERE id = ?", session["user_id"]
    )[0]["hash"]

    if request.method == "POST":
        # Get user's old password
        old_password = request.form.get("old_password")
        if not old_password:
            flash("Missing old password!", "danger")
            return render_template("change_password.html")

        # Get user's new password
        new_password = request.form.get("new_password")
        if not new_password:
            flash("Missing new password!", "danger")
            return render_template("change_password.html")

        # Check if the user has typed the correct old password
        if not check_password_hash(user_old_hash, old_password):
            flash("Incorrect old password!", "danger")
            return render_template("change_password.html")

        # Check if the new password and its confirmation matches
        if new_password != request.form.get("new_password_confirmation"):
            flash("Passwords don't match!", "danger")
            return render_template("change_password.html")

        # Securely hash the new password and update user's password in the database
        db.execute(
            "UPDATE users SET hash = ? WHERE id = ?",
            generate_password_hash(new_password),
            session["user_id"],
        )

        # Returns the user to the homepage and show an alert that password was changed successfully
        flash("Password Changed!", "success")
        return redirect("/account")

    else:
        return render_template("change_password.html")


@app.route("/delete_account", methods=["GET", "POST"])
@login_required
def delete_account():
    # Get user's hashed password
    user_hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[
        0
    ]["hash"]

    if request.method == "POST":
        # Get user's password
        password = request.form.get("password")
        if not password:
            flash("Missing password!", "danger")
            return render_template("delete_account.html")

        # Check if the user has typed the correct password
        if not check_password_hash(user_hash, password):
            flash("Incorrect password!", "danger")
            return render_template("delete_account.html")

        # Get user's delete confirmation
        delete_confirmation = request.form.get("delete_confirmation")

        # If the confirmation bar isn't blank
        if not delete_confirmation:
            flash("Missing confirmation!", "danger")
            return render_template("delete_account.html")

        # Check if the user has typed DELETE
        if delete_confirmation.lower() == "delete":
            # Delete the user's account and all of his related data
            delete_account_data(db, session["user_id"])
        else:
            flash("Invalid confirmation!", "danger")
            return render_template("delete_account.html")

        # Show an alert that the account was deleted successfully
        flash("Account Deleted!", "success")

        # Forget any user_id
        session.clear()

        return redirect("/")
    else:
        return render_template("delete_account.html")
