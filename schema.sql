CREATE TABLE users (
id INTEGER NOT NULL PRIMARY KEY,
username TEXT NOT NULL UNIQUE,
hash TEXT NOT NULL,
join_date TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE quizzes (
id INTEGER NOT NULL PRIMARY KEY,
creator_id INTEGER NOT NULL,
title TEXT NOT NULL,
description TEXT,
category TEXT NOT NULL CHECK (category IN (
'Programming',
'Mathematics',
'Science',
'History',
'Geography',
'Languages',
'Sports',
'Entertainment',
'General Knowledge',
'Other'
)),
visibility TEXT NOT NULL CHECK (visibility IN ('Public', 'Private')),
shuffle_mode TEXT NOT NULL CHECK (shuffle_mode IN ('On', 'Off')),
creation_date TEXT NOT NULL DEFAULT (datetime('now')),
updated_at TEXT NOT NULL DEFAULT (datetime('now')),
FOREIGN KEY (creator_id) REFERENCES users(id)
);

CREATE TABLE questions (
id INTEGER NOT NULL PRIMARY KEY,
quiz_id INTEGER NOT NULL,
order_num INTEGER NOT NULL,
text TEXT NOT NULL,
FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
);

CREATE TABLE choices (
id INTEGER NOT NULL PRIMARY KEY,
question_id INTEGER NOT NULL,
order_num INTEGER NOT NULL,
text TEXT NOT NULL,
type TEXT NOT NULL CHECK (type IN ('Correct', 'Incorrect')),
FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE TABLE rankings (
quiz_id INTEGER NOT NULL,
user_id INTEGER NOT NULL,
score INTEGER NOT NULL,
date TEXT NOT NULL DEFAULT (datetime('now')),
FOREIGN KEY (user_id) REFERENCES users(id),
FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
UNIQUE (quiz_id, user_id)
);
