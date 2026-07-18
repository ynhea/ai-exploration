from rag_utils import search_similar_chunks

# 계산 Tool (연차일수)
def calculate_annual_leave(years_of_service: float) -> dict:
    """
    근속연수(년)를 받아서 연차일수를 계산한다.
    - 1년 미만: 개근 가정 시 근속 개월 수만큼 1일씩 (최대 11일)
    - 1년 이상: 15일 + (2년마다 1일 가산), 최대 25일
    """
    # TODO: years_of_service < 1 인 경우 처리
    #   힌트: 개월 수 = years_of_service * 12, int()로 내림
    #   힌트: min(개월수, 11)
    days = 0
    if years_of_service < 1 :
        days = min(int(years_of_service * 12), 11)
    # TODO: years_of_service >= 1 인 경우 처리
    #   힌트: 가산일수 = (years_of_service - 1) // 2  (2년마다 1일)
    #   힌트: 15 + 가산일수, min(..., 25)
    else :
        add = (years_of_service - 1) // 2
        days = min(int(15 + add), 25)
    return {"years_of_service": years_of_service, "annual_leave_days": days}


# 검색 Tool (content 가드레일 추가)
def search_company_docs(question: str) -> dict:
    """
    사내 문서(취업규칙, 복지제도, 휴가정책)에서 질문과 관련된 내용을 검색한다.
    연차휴가 일수 계산 이외의 모든 정책성 질문(리프레시 휴가, 경조사 휴가, 복지제도, 근무시간, 
    수습기간, 퇴사절차 등)은 반드시 이 도구로 확인해야 하며, 다른 도구로는 알 수 없다.
    """
    # TODO: search_similar_chunks(question, top_k=3) 호출
    # TODO: results["documents"][0] 리스트를 하나의 문자열로 합치기 (Day3에서 했던 "\n\n---\n\n".join(...) 그대로 재사용 가능)
    # TODO: {"context": 합친 문자열} 형태로 반환
    results = search_similar_chunks(question, top_k=5)
    context = "\n\n---\n\n".join(results["documents"][0])
    
    # TODO: context가 빈 문자열이면, "관련 문서를 찾지 못했습니다" 같은 명시적 문구로 대체
    #   힌트: if not context: 로 체크
    if not context:
        context = "관련 문서를 찾지 못했습니다"
    
    return {"context": context}