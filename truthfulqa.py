# to run this script, run inspect eval truthfulqa.py --model hf/meta-llama/Meta-Llama-3-8B-Instruct in the cli

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, hf_dataset
from inspect_ai.scorer import scorer, accuracy, bootstrap_std
from inspect_ai.solver import multiple_choice, system_message, TaskState
from inspect_ai.scorer._target import Target
from inspect_ai.scorer._metric import Score

@scorer(metrics=[accuracy(), bootstrap_std()])
def logprob_based_scorer():
    async def score(state: TaskState, target: Target) -> Score:
        model_answer_full = state.output.completion.strip().upper()
        # Extract just the letter from the model's answer
        model_answer = model_answer_full.split(":")[-1].strip()
        
        # Handle the case where target.target is a list
        if isinstance(target.target, list):
            correct_answers = [ans.strip().upper() for ans in target.target]
        else:
            correct_answers = [str(target.target).strip().upper()]

        is_correct = model_answer in correct_answers

        logprobs = state.output.choices[0].logprobs

        if logprobs is None:
            return Score(
                value="C" if is_correct else "I",
                answer=model_answer,
                explanation=f"Model answer: {model_answer}, Correct answers: {correct_answers}, No logprobs available"
            )

        avg_logprob = sum(lp.logprob for lp in logprobs.content) / len(logprobs.content)

        return Score(
            value="C" if is_correct else "I",
            answer=model_answer,
            explanation=f"Model answer: {model_answer}, Correct answers: {correct_answers}, Average log probability: {avg_logprob:.4f}",
            metadata={"avg_logprob": avg_logprob}
        )

    return score

def labels_to_positions(labels: list[int]) -> list[str]:
    return [chr(ord("A") + i) for i, label in enumerate(labels) if label == 1]
 
@task
def truthfulqa(target="mc1"):
    def record_to_sample(record):
        return Sample(
            input=record["question"],
            choices=record[f"{target}_targets"]["choices"],
            target=labels_to_positions(record[f"{target}_targets"]["labels"]),
        )

    dataset = hf_dataset(
        path="ebayes/uhura-truthfulqa",
        name="multiple_choice",
        sample_fields=record_to_sample,
        split="test",
        shuffle=True,
    )

    if target == "mc1":
        multiple_correct = False
    else:
        multiple_correct = True

    return Task(
        dataset=dataset,
        plan=[
            multiple_choice(multiple_correct=multiple_correct, shuffle=True),
        ],
        scorer=logprob_based_scorer(),
    )