import os
import sys

# Add the project root to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from app.db.session import SessionLocal
# from app.models.candidate import Candidate


def generate_mock_resumes(count: int = 1000):
    print(f"Generating {count} mock candidate records for performance testing...")

    # db = SessionLocal()
    # try:
    #     for i in range(count):
    #         candidate = Candidate(
    #             name=f"Perf Test Candidate {i}",
    #             skills="Python, SQL, FastApi",
    #             score=0.85
    #         )
    #         db.add(candidate)
    #     db.commit()
    #     print("Seed complete.")
    # finally:
    #     db.close()

    print("Seed complete. (Uncomment DB logic once models are imported)")


if __name__ == "__main__":
    generate_mock_resumes()
