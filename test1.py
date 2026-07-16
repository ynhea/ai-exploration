from rag_utils import build_rag_prompt

print(build_rag_prompt("리프레시 휴가는 연차를 써야되는거야?", top_k=8))
print("=" * 50)
print(build_rag_prompt("퇴사는 어떻게 하면 돼?", top_k=8))