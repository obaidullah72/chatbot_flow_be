from django.contrib import admin

from .models import Answer, FollowUp, Question, Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['username', 'topic', 'language', 'created_at']
    list_filter = ['topic', 'language', 'created_at']
    search_fields = ['username', 'topic']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['session', 'question_index', 'question_text', 'created_at']
    list_filter = ['session__topic', 'created_at']
    search_fields = ['question_text']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['question', 'initial_score', 'final_score', 'average_score', 'completed_followups', 'created_at']
    list_filter = ['created_at', 'initial_score', 'average_score']
    search_fields = ['answer_text']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ['answer', 'followup_index', 'score', 'created_at']
    list_filter = ['created_at', 'score']
    search_fields = ['question_text', 'answer_text']
