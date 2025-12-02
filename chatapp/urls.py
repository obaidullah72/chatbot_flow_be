from django.urls import path

from . import views

urlpatterns = [
    path("questions/", views.generate_questions_view, name="generate-questions"),
    path("answer/", views.answer_view, name="answer"),
    path("answer/finalize/", views.finalize_followups_view, name="answer-finalize"),
    path("answer/continue/", views.continue_followups_view, name="answer-continue"),
    path("question/repeat/", views.repeat_question_view, name="repeat-question"),
]

