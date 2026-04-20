import json
from app.core.flashcard_gen import generate_flashcards

dummy_chunks = [
    (
        "Photosynthesis is the process by which green plants, algae, and some bacteria "
        "convert light energy into chemical energy stored as glucose. It occurs mainly in "
        "the chloroplasts and requires carbon dioxide, water, and sunlight. The overall "
        "reaction produces glucose and oxygen as a byproduct."
    ),
    (
        "Mitosis is a type of cell division resulting in two daughter cells with the same "
        "number of chromosomes as the parent cell. It has four main phases: prophase, "
        "metaphase, anaphase, and telophase. Mitosis is used for growth and tissue repair."
    ),
    (
        "DNA (deoxyribonucleic acid) carries the genetic instructions for all living "
        "organisms. It is a double helix made of nucleotide base pairs: adenine pairs with "
        "thymine, and cytosine pairs with guanine. Genes are specific sequences of DNA that "
        "encode proteins."
    ),
]

print("Calling Groq to generate flashcards...\n")
cards = generate_flashcards(dummy_chunks, topic_hint="Biology basics")

print(f"Generated {len(cards)} flashcards:\n")
for i, card in enumerate(cards, 1):
    print(f"Card {i}")
    print(f"  Q: {card['front']}")
    print(f"  A: {card['back']}")
    print()

print("Raw JSON output:")
print(json.dumps(cards, indent=2))
