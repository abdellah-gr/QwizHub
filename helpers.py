import requests

from database import DB
from datetime import datetime
from flask import flash, redirect, render_template, session
from functools import wraps


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def update_quiz_timestamp(db, quiz_id):
    # Update quiz timestamp
    db.execute(
        "UPDATE quizzes SET updated_at = ? WHERE id = ?", datetime.now(), quiz_id
    )


def clear_ranking(db, quiz_id):
    # Clear quiz ranking
    db.execute("DELETE FROM rankings WHERE quiz_id = ?", quiz_id)


def quiz_modified(db, quiz_id):
    clear_ranking(db, quiz_id)
    update_quiz_timestamp(db, quiz_id)


def delete_quiz_data(db, quiz_id):
    # Delete all the the choices from all the questions in a quiz
    db.execute(
        """
        DELETE FROM choices WHERE question_id IN (
        SELECT id FROM questions WHERE quiz_id = ?
        )
        """,
        quiz_id,
    )

    # Delete all the questions from the quiz
    db.execute("DELETE FROM questions WHERE quiz_id = ?", quiz_id)

    clear_ranking(db, quiz_id)

    # Delete the quiz from the database
    db.execute("DELETE FROM quizzes WHERE id = ?", quiz_id)


def delete_question_data(db, question_id):
    # Delete all the choices of the question that will be deleted
    db.execute("DELETE FROM choices WHERE question_id = ?", question_id)

    # Delete the question from the quiz
    db.execute("DELETE FROM questions WHERE id = ?", question_id)


def delete_account_data(db, user_id):
    # Delete all the the choices from the user's quizzes
    db.execute(
        """
        DELETE FROM choices WHERE question_id IN (
        SELECT id FROM questions WHERE quiz_id IN (
        SELECT id FROM quizzes WHERE creator_id = ?
        ))
        """,
        user_id,
    )

    # Delete all the the questions from the user's quizzes
    db.execute(
        """
        DELETE FROM questions WHERE quiz_id IN (
        SELECT id FROM quizzes WHERE creator_id = ?
        )
        """,
        user_id,
    )

    # Delete user's entries in rankings
    db.execute("DELETE FROM rankings WHERE user_id = ?", user_id)

    # Delete user's quizzes
    db.execute("DELETE FROM quizzes WHERE creator_id = ?", user_id)

    # Delete user from the database
    db.execute("DELETE FROM users WHERE id = ?", user_id)
