from rag_utils import search_similar_chunks, build_rag_prompt
from llm_client import client

# 테스트 케이스
test_cases = [
    {"question": "건강을 지원해주는 제도가 있어?", "answer_keywords": ["건강검진", "심리상담"]},
    {"question": "성장을 지원해주는 제도가 있어?", "answer_keywords": ["도서구입비", "외부 교육"]},
    {"question": "식대는 얼마야?", "answer_keywords": ["15만원"]},
    {"question": "연차는 며칠이야?", "answer_keywords": ["25일"]},
    {"question": "경조사일 경우에는 얼마나 쉴 수 있어?", "answer_keywords": ["7일"]},
    {"question": "리프레시 휴가는 연차를 써야되는거야?", "answer_keywords": ["별도"]},
    {"question": "반차는 어떻게 사용해야돼?", "answer_keywords": ["4시간", "1일 전"]},
    {"question": "재택근무도 가능해?", "answer_keywords": ["주 2회"]},
    {"question": "수습기간 특이사항이 뭐야?", "answer_keywords": ["3개월", "80%"]},
    {"question": "퇴사는 어떻게 하면 돼?", "answer_keywords": ["30일", "인수인계"]},
]

# 검색 단계 테스트
def eval_retrieval(test_cases : list, top_k : int):
    """검색된 chunk들 안에 keyword가 하나라도 있으면 성공"""
    # TODO: 각 test_case마다 search_similar_chunks() 호출
    # TODO: results["documents"][0]를 합친 문자열에 keyword가 포함되는지 확인
    # TODO: 성공/실패 개수 세서 정확도(%) 반환
    success = 0
    for case in test_cases:
        results = search_similar_chunks(case["question"], top_k)
        context = "\n\n---\n\n".join(results["documents"][0])
        for keyword in case["answer_keywords"]:
            if keyword in context:  
                success += 1
                break
    rate = (success / len(test_cases)) * 100
    return rate

# 생성 단계 테스트
def eval_generation(test_cases: list, top_k: int):
    """최종 LLM 답변에 keyword가 하나라도 있으면 성공"""
    success = 0
    fail_logs = []
    for case in test_cases:
        prompt = build_rag_prompt(case["question"], top_k=top_k)
        # TODO: Groq client로 completion 생성 (main.py의 로직 참고)
        # TODO: completion.choices[0].message.content 에서 답변 텍스트 꺼내기
        # TODO: answer_keywords 중 하나라도 답변에 포함되면 success += 1
        messages = [
            {"role": "system", "content": "너는 사내 챗봇이다. 참고자료를 바탕으로 답하고, 모르면 모른다고 답하라."}
            ] + [{"role": "user", "content": prompt}]
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = completion.choices[0].message.content
        matched = any(keyword in reply for keyword in case["answer_keywords"])
        if matched:
            success += 1
        else:
            fail_logs.append({"question": case["question"], "reply": reply, "expected": case["answer_keywords"]})
    rate = (success / len(test_cases)) * 100
    return rate, fail_logs


if __name__ == "__main__":
    k= 5
    r_rate = eval_retrieval(test_cases, k)
    g_rate = eval_generation(test_cases, k)
    print(r_rate)
    print()
    print(g_rate)











