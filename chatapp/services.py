from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .models import Answer, FollowUp, Question, Session

MIN_FOLLOW_UP_COUNT = 1
FOLLOW_UP_COUNT = 8
DEFAULT_LANGUAGE = "en"
QUESTION_COUNT = 10


@dataclass
class FollowUpPair:
    question: str
    answer: str


def evaluate_single_answer_with_attachment(
    *,
    topic: str,
    user: str,
    question: str,
    answer_text: str,
    language: str = DEFAULT_LANGUAGE,
    sub_dialogue: Sequence[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """
    Heuristic scoring helper that mimics an external evaluator.

    The goal is to approximate a human auditor using only local logic, without
    depending on any external LLM service. The scoring tries to balance:
    - relevance to the question (keyword coverage)
    - depth and length (enough words, not just a one‑liner)
    - structure (sentences and basic organization)
    - clarity (proper sentence endings)
    """

    normalized_answer = answer_text.strip()
    word_count = len(normalized_answer.split())

    if word_count == 0:
        return {
            "score": 0.0,
            "feedback": "No answer was provided.",
            "topic": topic,
            "user": user,
            "question": question,
            "language": language,
            "sub_dialogue": list(sub_dialogue or []),
        }

    # 1) Length / depth: encourage at least 60–80 words
    length_score = min(5.0, word_count / 15.0)  # roughly 0–5

    # 2) Coverage of question terms
    coverage_penalty = _coverage_penalty(question, normalized_answer)

    # 3) Basic structure: sentences & paragraphs
    sentence_endings = sum(normalized_answer.count(ch) for ch in [".", "!", "?"])
    structure_bonus = 0.0
    if sentence_endings >= 2:
        structure_bonus += 1.0
    if "\n" in normalized_answer:
        structure_bonus += 0.5

    # 4) Tiny bonus if there is meaningful follow-up dialogue
    followup_bonus = 0.0
    if sub_dialogue:
        followup_bonus = min(1.0, len(sub_dialogue) * 0.25)

    raw_score = length_score + structure_bonus + followup_bonus - coverage_penalty
    score = max(0.0, min(10.0, round(raw_score, 1)))

    if score >= 8:
        feedback = "Strong, detailed answer with good structure and coverage of the question."
    elif score >= 5:
        feedback = "Reasonable answer with okay coverage. It could be improved with more concrete detail and clearer structure."
    else:
        feedback = (
            "Answer is too shallow or not clearly connected to the question. "
            "Add concrete examples, explain key terms, and address all parts of the prompt."
        )

    return {
        "score": score,
        "feedback": feedback,
        "topic": topic,
        "user": user,
        "question": question,
        "language": language,
        "sub_dialogue": list(sub_dialogue or []),
    }


def generate_follow_up_question_set(
    *,
    topic: str,
    user: str,
    original_question: str,
    original_answer: str,
    language: str = DEFAULT_LANGUAGE,
    min_questions: int = FOLLOW_UP_COUNT,
    max_questions: int = FOLLOW_UP_COUNT,
) -> List[str]:
    """Generate a varied batch of follow-up prompts using random selection."""

    target_count = max(min_questions, min(max_questions, FOLLOW_UP_COUNT))
    scaffolding = _followup_scaffolding()
    context_snippet = original_question[:60].strip()

    followups: List[str] = []
    for idx in range(target_count):
        # Select category and random variation
        category_index = idx % len(scaffolding)
        category_variations = scaffolding[category_index]
        selected_template = random.choice(category_variations)
        followups.append(
            f"{selected_template} (Regarding {topic}: {context_snippet})"
        )

    return followups[:target_count]


def generate_next_follow_up_question(
    *,
    topic: str,
    user: str,
    original_question: str,
    original_answer: str,
    language: str = DEFAULT_LANGUAGE,
    asked_count: int = 0,
) -> str:
    """
    Generate the *next* follow-up question based on how many have already been asked.
    Uses random selection from variations to ensure different questions each time.

    This allows an iterative flow:
      - backend sends first follow-up
      - user answers
      - backend generates second follow-up based on the updated context, etc.
    """

    scaffolding = _followup_scaffolding()
    
    # Select question category based on asked_count (cycle through categories)
    category_index = asked_count % len(scaffolding)
    category_variations = scaffolding[category_index]
    
    # Randomly select one variation from the category to ensure variety
    selected_template = random.choice(category_variations)
    
    # Add context about topic and original question for better relevance
    context_snippet = original_question[:60].strip()
    return f"{selected_template} (Regarding {topic}: {context_snippet})"


def _followup_scaffolding() -> List[List[str]]:
    """
    Returns multiple variations of follow-up question templates.
    Each sub-list contains variations of the same type of question.
    """
    return [
        # Examples & Evidence
        [
        "Can you list concrete examples that support your earlier point?",
            "Could you provide specific examples to illustrate what you mentioned?",
            "What real-world examples can you give to back up your statement?",
            "Can you share some concrete instances that demonstrate your point?",
        ],
        # Data & Citations
        [
        "What data or citations back up your response?",
            "What evidence or sources support your answer?",
            "Can you provide any data or references that validate your point?",
            "What research or documentation supports what you've said?",
        ],
        # Expansion & Clarity
        [
        "Where could the initial answer be expanded for clarity?",
            "What parts of your answer could use more detail or explanation?",
            "Which aspects would benefit from a deeper explanation?",
            "What additional context would make your answer clearer?",
        ],
        # Edge Cases & Counter-arguments
        [
        "Are there edge cases or counter-arguments you did not cover?",
            "What edge cases or exceptions should be considered?",
            "Are there any scenarios where your answer might not apply?",
            "What alternative perspectives or counter-arguments exist?",
        ],
        # Beginner Explanation
        [
        "How would you explain this to a beginner in one paragraph?",
            "Can you simplify this explanation for someone new to the topic?",
            "How would you make this more accessible to a beginner?",
            "What's a beginner-friendly way to explain this concept?",
        ],
        # Practical Steps
        [
        "Which practical steps should the user take next?",
            "What are the next steps someone should follow?",
            "What actionable steps would you recommend?",
            "What would be the practical next steps in this situation?",
        ],
        # Risks & Unknowns
        [
        "Summarize the critical risks or unknowns that remain.",
            "What are the main risks or uncertainties to be aware of?",
            "What potential issues or unknowns should be considered?",
            "What are the key risks or gaps that need attention?",
        ],
        # Checklist & Summary
        [
        "Provide a concise checklist the user can follow.",
            "Can you create a step-by-step checklist for this?",
            "What would a practical checklist look like for this?",
            "Can you summarize this as a clear, actionable checklist?",
        ],
        # Implementation Details
        [
            "What are the specific implementation details you would focus on?",
            "Can you elaborate on the technical implementation aspects?",
            "What are the key technical details needed for implementation?",
            "What implementation considerations are most important?",
        ],
        # Troubleshooting
        [
            "What common issues might arise and how would you handle them?",
            "What problems could occur and what are the solutions?",
            "What troubleshooting steps would you recommend?",
            "How would you handle potential issues or errors?",
        ],
    ]


def handle_question_flow(
    *,
    topic: str,
    user: str,
    question: str,
    main_answer: str,
    language: str = DEFAULT_LANGUAGE,
    question_index: int | None = None,
) -> Dict[str, Any]:
    """
    Handle initial answer submission.
    NO evaluation yet - just save answer and ask first follow-up.
    Evaluation will happen after all 8 follow-ups are answered.
    """

    # Save to database WITHOUT evaluation
    answer_id = None
    try:
        session, _ = Session.objects.get_or_create(
            username=user,
        topic=topic,
        language=language,
        )
        
        question_obj, _ = Question.objects.get_or_create(
            session=session,
            question_index=question_index or 0,
            defaults={"question_text": question}
        )
        
        answer_obj = Answer.objects.create(
            question=question_obj,
            answer_text=main_answer,
            target_followups=FOLLOW_UP_COUNT,  # Always 8 follow-ups
        )
        answer_id = answer_obj.id
    except Exception:
        pass  # Continue even if database save fails

    # Generate first follow-up question
    first_followup = generate_next_follow_up_question(
        topic=topic,
        user=user,
        original_question=question,
        original_answer=main_answer,
        language=language,
        asked_count=0,
    )

    # Save first follow-up question to database (even before answer is given)
    if answer_id:
        try:
            answer_obj = Answer.objects.get(id=answer_id)
            # Save the follow-up question (answer will be saved later when user responds)
            FollowUp.objects.get_or_create(
                answer=answer_obj,
                followup_index=0,
                defaults={
                    "question_text": first_followup,
                    "answer_text": "",  # Empty for now, will be filled when user answers
                }
            )
        except Answer.DoesNotExist:
            pass

    return {
        "needs_followups": True,
        "follow_ups": [first_followup],
        "followup_index": 1,
        "max_followups": FOLLOW_UP_COUNT,
        "target_followups": FOLLOW_UP_COUNT,  # Always 8
        "answer_id": answer_id,  # Pass to continue_followups
        "consultant_note": (
            "I need to ask you 8 clarification questions before I can evaluate your answer. Let's start!"
        ),
    }


def finalize_followups(
    *,
    topic: str,
    user: str,
    question: str,
    main_answer: str,
    followup_pairs: Sequence[Dict[str, str]] | Sequence[FollowUpPair],
    language: str = DEFAULT_LANGUAGE,
) -> Dict[str, Any]:
    """Compute the final score after the follow-up answers."""

    normalized_pairs = [
        {"question": pair["question"], "answer": pair["answer"]}
        if isinstance(pair, dict)
        else {"question": pair.question, "answer": pair.answer}
        for pair in followup_pairs
    ]

    final_eval = evaluate_single_answer_with_attachment(
        topic=topic,
        user=user,
        question=question,
        answer_text=main_answer,
        language=language,
        sub_dialogue=normalized_pairs,
    )

    return {
        "final_score": final_eval["score"],
        "feedback": final_eval["feedback"],
        "evaluation": final_eval,
    }


def evaluate_answer_individually(
    *,
    question_text: str,
    answer_text: str,
    language: str = DEFAULT_LANGUAGE,
) -> Dict[str, Any]:
    """
    Evaluate a single answer (original or follow-up) independently.
    Returns score and feedback.
    """
    normalized_answer = answer_text.strip()
    word_count = len(normalized_answer.split())

    if word_count == 0:
        return {
            "score": 0.0,
            "feedback": "No answer was provided.",
        }

    # 1) Length / depth: encourage at least 60–80 words
    length_score = min(5.0, word_count / 15.0)  # roughly 0–5

    # 2) Coverage of question terms
    coverage_penalty = _coverage_penalty(question_text, normalized_answer)

    # 3) Basic structure: sentences & paragraphs
    sentence_endings = sum(normalized_answer.count(ch) for ch in [".", "!", "?"])
    structure_bonus = 0.0
    if sentence_endings >= 2:
        structure_bonus += 1.0
    if "\n" in normalized_answer:
        structure_bonus += 0.5

    raw_score = length_score + structure_bonus - coverage_penalty
    score = max(0.0, min(10.0, round(raw_score, 1)))

    if score >= 8:
        feedback = "Strong, detailed answer with good structure and coverage of the question."
    elif score >= 5:
        feedback = "Reasonable answer with okay coverage. It could be improved with more concrete detail and clearer structure."
    else:
        feedback = (
            "Answer is too shallow or not clearly connected to the question. "
            "Add concrete examples, explain key terms, and address all parts of the prompt."
        )

    return {
        "score": score,
        "feedback": feedback,
    }


def calculate_average_score(
    *,
    original_score: float,
    followup_scores: List[float],
) -> float:
    """
    Calculate the average score from the original answer and all follow-up answers.
    """
    if not followup_scores:
        return original_score
    
    all_scores = [original_score] + followup_scores
    return round(sum(all_scores) / len(all_scores), 1)


def continue_followups(
    *,
    topic: str,
    user: str,
    question: str,
    main_answer: str,
    followup_pairs: Sequence[Dict[str, str]] | Sequence[FollowUpPair],
    language: str = DEFAULT_LANGUAGE,
    target_followups: int | None = None,
    answer_id: int | None = None,
) -> Dict[str, Any]:
    """
    Iterative follow-up flow:

    - NO evaluation until all 8 follow-ups are answered
    - Just save follow-up answers as they come
    - After 8 follow-ups are complete, evaluate ALL answers together:
      * 1 original answer
      * 8 follow-up answers
    - Calculate and return average score from all 9 evaluations
    """

    normalized_pairs = [
        {"question": pair["question"], "answer": pair["answer"]}
        if isinstance(pair, dict)
        else {"question": pair.question, "answer": pair.answer}
        for pair in followup_pairs
    ]

    asked_count = len(normalized_pairs)
    plan_target = _normalize_followup_target(target_followups or FOLLOW_UP_COUNT)

    # Save follow-ups to database (without evaluation yet)
    if answer_id:
        try:
            answer_obj = Answer.objects.get(id=answer_id)
            answer_obj.completed_followups = asked_count
            
            # Save/update follow-ups (question and answer both)
            for idx, pair in enumerate(normalized_pairs):
                followup_obj, created = FollowUp.objects.get_or_create(
                    answer=answer_obj,
                    followup_index=idx,
                    defaults={
                        "question_text": pair["question"],  # Save follow-up question
                        "answer_text": pair["answer"],  # Save follow-up answer
                    }
                )
                if not created:
                    # Update existing follow-up
                    followup_obj.question_text = pair["question"]  # Update question text
                    followup_obj.answer_text = pair["answer"]  # Update answer text
                    followup_obj.save()
            
            answer_obj.save()
        except Answer.DoesNotExist:
            pass  # Continue without saving if answer not found

    # Check if all 8 follow-ups are complete
    should_finalize = asked_count >= FOLLOW_UP_COUNT

    if should_finalize:
        # NOW evaluate everything together: 1 original + 8 follow-ups
        
        # Evaluate original answer
        original_eval = evaluate_answer_individually(
            question_text=question,
        answer_text=main_answer,
        language=language,
        )
        original_score = original_eval["score"]

        # Evaluate each follow-up answer
        followup_scores = []
        followup_evaluations = []
        for pair in normalized_pairs:
            followup_eval = evaluate_answer_individually(
                question_text=pair["question"],
                answer_text=pair["answer"],
                language=language,
            )
            followup_scores.append(followup_eval["score"])
            followup_evaluations.append({
                "question": pair["question"],
                "answer": pair["answer"],
                "score": followup_eval["score"],
                "feedback": followup_eval["feedback"],
            })

        # Calculate average score from all 9 evaluations (1 original + 8 follow-ups)
        average_score = calculate_average_score(
            original_score=original_score,
            followup_scores=followup_scores,
        )

        # Save all evaluations to database
        if answer_id:
            try:
                answer_obj = Answer.objects.get(id=answer_id)
                answer_obj.initial_score = original_score
                answer_obj.initial_feedback = original_eval["feedback"]
                answer_obj.final_score = average_score
                answer_obj.average_score = average_score
                answer_obj.completed_followups = asked_count
                answer_obj.final_feedback = f"Average score from 1 original answer and {asked_count} follow-ups: {average_score}/10"
                answer_obj.save()
                
                # Update follow-ups with scores
                for idx, (pair, followup_eval) in enumerate(zip(normalized_pairs, followup_evaluations)):
                    followup_obj = FollowUp.objects.get(
                        answer=answer_obj,
                        followup_index=idx,
                    )
                    followup_obj.score = followup_eval["score"]
                    followup_obj.feedback = followup_eval["feedback"]
                    followup_obj.save()
            except (Answer.DoesNotExist, FollowUp.DoesNotExist):
                pass  # Continue even if database save fails

        return {
            "needs_followups": False,
            "final_score": average_score,
            "original_score": original_score,
            "followup_scores": followup_scores,
            "average_score": average_score,
            "feedback": f"Evaluation complete! Average score calculated from 1 original answer ({original_score}/10) and {asked_count} follow-ups ({', '.join(map(str, followup_scores))}/10 each).",
            "evaluation": {
                "original": original_eval,
                "followups": followup_evaluations,
            },
            "followup_index": asked_count,
            "max_followups": FOLLOW_UP_COUNT,
            "target_followups": FOLLOW_UP_COUNT,
        }

    # Not all follow-ups answered yet - ask next one
    next_followup = generate_next_follow_up_question(
        topic=topic,
        user=user,
        original_question=question,
        original_answer=main_answer,
        language=language,
        asked_count=asked_count,
    )

    # Save next follow-up question to database (even before answer is given)
    if answer_id:
        try:
            answer_obj = Answer.objects.get(id=answer_id)
            # Save the follow-up question (answer will be saved when user responds)
            FollowUp.objects.get_or_create(
                answer=answer_obj,
                followup_index=asked_count,  # Current follow-up index
                defaults={
                    "question_text": next_followup,
                    "answer_text": "",  # Empty for now, will be filled when user answers
                }
            )
        except Answer.DoesNotExist:
            pass

    return {
        "needs_followups": True,
        "follow_ups": [next_followup],
        "followup_index": asked_count + 1,
        "max_followups": FOLLOW_UP_COUNT,
        "target_followups": FOLLOW_UP_COUNT,
        "consultant_note": f"Please answer this clarification question ({asked_count + 1} of {FOLLOW_UP_COUNT}). After all {FOLLOW_UP_COUNT} follow-ups, I'll evaluate everything together.",
    }


def _coverage_penalty(question: str, answer: str) -> float:
    """Penalize answers that do not reuse question keywords."""

    question_terms = {token.lower() for token in question.split() if len(token) > 3}
    if not question_terms:
        return 0

    matches = sum(1 for term in question_terms if term in answer.lower())
    coverage_ratio = matches / len(question_terms)
    if coverage_ratio >= 0.6:
        return 0
    if coverage_ratio >= 0.3:
        return 1
    return 2


def generate_question_set(
    *,
    topic: str,
    count: int = QUESTION_COUNT,
    language: str = DEFAULT_LANGUAGE,
) -> List[str]:
    """
    Generate a **set of unique, high-quality practice questions** for a topic.
    Uses random selection from a large pool of varied templates to ensure
    different questions each time.
    """

    safe_count = max(1, min(count, QUESTION_COUNT))
    
    # Large pool of varied question templates
    all_templates = [
        # Core concepts
        "Explain the core concept of {topic} and when you would use it.",
        "What is {topic} and what problem does it solve?",
        "Describe the fundamental principles behind {topic}.",
        "What are the key characteristics that define {topic}?",
        
        # Architecture & Design
        "Describe the main building blocks or architecture of a typical {topic} solution.",
        "What is the typical structure or design pattern used in {topic}?",
        "How is {topic} typically organized or structured?",
        "What components make up a standard {topic} implementation?",
        
        # Code & Implementation
        "Show a short code example that demonstrates {topic} in practice and explain it line by line.",
        "Write a simple example showing how {topic} works in code.",
        "Demonstrate {topic} with a practical code snippet and explain each part.",
        "Provide a code example that illustrates the basic usage of {topic}.",
        
        # Comparisons & Trade-offs
        "What are the biggest advantages and disadvantages of using {topic} compared to alternatives?",
        "How does {topic} compare to similar technologies or approaches?",
        "What are the pros and cons of choosing {topic} for a project?",
        "When should you use {topic} versus other options?",
        
        # Real-world Applications
        "Describe a realistic real-world application where {topic} is a great fit and explain why.",
        "Give an example of a practical scenario where {topic} would be the best choice.",
        "What types of projects or problems benefit most from using {topic}?",
        "Describe a real-world use case for {topic} and explain the benefits.",
        
        # Common Issues & Mistakes
        "Explain common mistakes or pitfalls developers face when working with {topic}, and how to avoid them.",
        "What are the most frequent errors people make with {topic} and how can they be prevented?",
        "What should developers be careful about when using {topic}?",
        "What are common gotchas or traps when working with {topic}?",
        
        # Integration & Ecosystem
        "How does {topic} interact with or depend on other key technologies in its ecosystem?",
        "What other technologies or tools work well with {topic}?",
        "How does {topic} fit into the broader technology landscape?",
        "What dependencies or integrations are typically needed for {topic}?",
        
        # Debugging & Problem-solving
        "Imagine a bug caused by incorrect use of {topic}. How would you debug and fix it?",
        "If something goes wrong with {topic}, what steps would you take to troubleshoot?",
        "Describe a debugging scenario involving {topic} and how you would resolve it.",
        "What debugging strategies work best for {topic}-related issues?",
        
        # Teaching & Explanation
        "How would you teach {topic} to a beginner who already knows basic programming?",
        "Explain {topic} as if you were teaching it to someone new to the concept.",
        "How would you introduce {topic} to a colleague who has never used it?",
        "What's the best way to explain {topic} to someone unfamiliar with it?",
        
        # Summary & Best Practices
        "Summarize {topic} in a concise paragraph, then list a few advanced tips or best practices.",
        "Give a brief overview of {topic} and share some expert-level recommendations.",
        "Provide a summary of {topic} along with some best practices for using it effectively.",
        "What are the key points about {topic} and what advanced techniques should developers know?",
        
        # Performance & Optimization
        "What are the performance characteristics of {topic} and how can it be optimized?",
        "How does {topic} perform under different conditions and what affects its efficiency?",
        "What optimization techniques are relevant when working with {topic}?",
        
        # Security & Best Practices
        "What security considerations should developers keep in mind when using {topic}?",
        "What are the security implications of using {topic} and how can risks be mitigated?",
        "How should {topic} be used securely in production environments?",
    ]
    
    # Randomly select templates to ensure variety each time
    selected_templates = random.sample(all_templates, min(safe_count, len(all_templates)))
    
    # Format with topic
    questions = [template.format(topic=topic) for template in selected_templates]
    
    return questions


def _planned_followup_target(initial_score: float) -> int:
    """
    Decide how many consultant-style follow-ups should happen before
    locking a score. Strong answers still get at least one clarifying
    prompt, while weaker ones can receive up to eight.
    """

    if initial_score >= 8:
        return MIN_FOLLOW_UP_COUNT
    if initial_score >= 6:
        return 2
    if initial_score >= 4:
        return 4
    if initial_score >= 2:
        return 6
    return FOLLOW_UP_COUNT


def _normalize_followup_target(target: int | None) -> int:
    """
    Clamp caller-provided follow-up targets to the supported range so the
    flow remains predictable and bounded.
    """

    if target is None:
        return FOLLOW_UP_COUNT

    try:
        parsed = int(target)
    except (TypeError, ValueError):
        return FOLLOW_UP_COUNT

    return max(MIN_FOLLOW_UP_COUNT, min(FOLLOW_UP_COUNT, parsed))

