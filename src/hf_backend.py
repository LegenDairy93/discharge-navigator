"""HuggingFace Transformers backend for MedGemma inference.

Drop-in alternative to Ollama for environments like Kaggle
where Ollama is unavailable but a T4 GPU is.
"""
import torch

DEFAULT_HF_MODEL = "google/medgemma-4b-it"

_model_cache = {"model": None, "tokenizer": None}


def load_medgemma(model_id: str = DEFAULT_HF_MODEL):
    """Load MedGemma with bfloat16 on GPU. Returns (model, tokenizer).

    Uses AutoModelForCausalLM (text-only, no vision encoder overhead).
    Caches after first load.
    """
    if _model_cache["model"] is not None:
        return _model_cache["model"], _model_cache["tokenizer"]

    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading {model_id} (bfloat16, device_map=auto)...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()
    print(f"Model loaded on {model.device}")

    _model_cache["model"] = model
    _model_cache["tokenizer"] = tokenizer
    return model, tokenizer


def hf_chat(
    model,
    tokenizer,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_new_tokens: int = 4096,
) -> str:
    """Generate a response using HuggingFace model. Returns raw text."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    try:
        input_ids = tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True
        ).to(model.device)
    except Exception:
        # Some models don't support system role -- merge into user
        messages = [{"role": "user", "content": f"{system}\n\n{user}"}]
        input_ids = tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True
        ).to(model.device)

    do_sample = temperature > 0
    gen_kwargs = dict(
        max_new_tokens=max_new_tokens,
        do_sample=do_sample,
    )
    if do_sample:
        gen_kwargs["temperature"] = temperature

    with torch.no_grad():
        outputs = model.generate(input_ids, **gen_kwargs)

    # Decode only the new tokens (skip the prompt)
    new_tokens = outputs[0][input_ids.shape[1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return response


def is_gpu_available() -> bool:
    """Check if a CUDA GPU is available."""
    return torch.cuda.is_available()
