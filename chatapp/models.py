from django.db import models


class Session(models.Model):
    """Represents a practice session for a user on a specific topic."""
    
    username = models.CharField(max_length=200)
    topic = models.CharField(max_length=200)
    language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username', 'topic']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.topic} ({self.created_at.date()})"


class Question(models.Model):
    """A question within a session."""
    
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_index = models.IntegerField()  # 0-based index in the session
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['session', 'question_index']
        unique_together = [['session', 'question_index']]
        indexes = [
            models.Index(fields=['session', 'question_index']),
        ]
    
    def __str__(self):
        return f"Q{self.question_index + 1}: {self.question_text[:50]}..."


class Answer(models.Model):
    """A main answer to a question, with scoring information."""
    
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    initial_score = models.FloatField(null=True, blank=True)
    final_score = models.FloatField(null=True, blank=True)
    average_score = models.FloatField(null=True, blank=True)  # Average of original + all follow-ups
    initial_feedback = models.TextField(blank=True)
    final_feedback = models.TextField(blank=True)
    target_followups = models.IntegerField(default=1)
    completed_followups = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['question', 'created_at']),
        ]
    
    def __str__(self):
        return f"Answer to Q{self.question.question_index + 1} (score: {self.average_score or self.final_score or self.initial_score})"


class FollowUp(models.Model):
    """A follow-up question-answer pair within an answer evaluation."""
    
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name='followups')
    question_text = models.TextField()
    answer_text = models.TextField()
    score = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    followup_index = models.IntegerField()  # 0-based index within the answer
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['answer', 'followup_index']
        unique_together = [['answer', 'followup_index']]
        indexes = [
            models.Index(fields=['answer', 'followup_index']),
        ]
    
    def __str__(self):
        return f"Follow-up {self.followup_index + 1} (score: {self.score})"
