from sentence_transformers import SentenceTransformer
import chromadb

# 문장을 chunk단위로 분할
def split_into_chunks(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """
    text를 chunk_size 글자 단위로 나누되, overlap만큼 겹치게 나눈다.
    예: chunk_size=300, overlap=50이면
    0~300, 250~550, 500~800 ... 이런 식으로 겹치며 잘라야 함.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap은 chunk_size보다 작아야 합니다!")
    
    # TODO: 여기를 채워보세요
    # 힌트: while문으로 start 인덱스를 옮겨가며 text[start:start+chunk_size]를 잘라내면 됩니다.
    # 힌트: start += (chunk_size - overlap) 로 다음 시작점을 옮깁니다.
    start = 0
    chunk_list = []
    while start < len(text) :
        end = start + chunk_size
        chunk_list.append(text[start:end])
        start = end - overlap
    return chunk_list


# 모델 재사용 설정
# - 문장을 숫자로 바꿔주는 AI모델을 RAM에 올림
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ChromaDB 클라이언트 생성
# - 컴퓨터가 꺼져도 데이터가 사라지지 않도록 로컬에 영구적으로 저장
# - 그 중 company_docs(테이블/폴더 개념)이라는 데이터 저장공간을 지정
chroma_client = chromadb.PersistentClient(path="./chroma_db")
# chroma_client.delete_collection(name="company_docs")
collection = chroma_client.get_or_create_collection(name="company_docs")

# 문서 벡터화 & ChromaDB에 저장
def add_documents_to_db(doc_filenames: list[str]):
    """
    doc_filenames 안의 각 파일을 읽어서
    chunk로 나누고, embedding해서 ChromaDB에 저장한다.
    """
    for filename in doc_filenames:
        # TODO 1: 파일 읽기
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
        # TODO 2: split_into_chunks로 chunk 나누기
        chunks = split_into_chunks(text, chunk_size=100, overlap=50)
        # TODO 3: 각 chunk를 embedding_model.encode(chunk)로 벡터화
        vectors = embedding_model.encode(chunks)
        # TODO 4: collection.add(...)로 저장
        #   힌트: collection.add()는 ids, embeddings, documents, metadatas를 키워드 인자로 받습니다.
        #   ids: 각 chunk의 고유 id (예: "휴가정책_0", "휴가정책_1"...)
        #   embeddings: 벡터 리스트
        #   documents: chunk 원문 텍스트 리스트
        #   metadatas: [{"source": filename}, ...] 같은 부가정보
        ids = [f"{filename}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename} for i in range(len(chunks))]
        collection.add(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)
    return

# 검색 함수
def search_similar_chunks(question: str, top_k: int = 3):
    """
    question을 embedding해서 ChromaDB에서 가장 유사한 chunk를 top_k개 찾아 반환한다.
    """
    # TODO 1: question을 벡터화
    # 힌트: encode()는 리스트를 넣으면 리스트의 벡터들을 반환하니, 질문 하나만 넣어도 [question] 처럼 리스트로 감싸는 게 안전합니다.
    question_vector = embedding_model.encode([question])

    # TODO 2: collection.query()로 검색
    # 힌트: collection.query(query_embeddings=..., n_results=top_k) 형태
    results = collection.query(
        query_embeddings=question_vector,
        n_results=top_k
    )

    return results


# RAG - 프롬프트 연결
def build_rag_prompt(question: str, top_k: int = 3) -> str:
    # 질문에 대해 관련 chunk를 검색하고, 하나의 문자열로 합쳐서 반환
    results = search_similar_chunks(question, top_k=top_k)
    context = "\n\n---\n\n".join(results["documents"][0])
    
    # TODO 2: context와 question을 합쳐 최종 프롬프트 만들기
    prompt = f"""
        다음은 사내 문서에서 검색된 참고 자료입니다:
        ---
        {context}
        ---
        위 자료를 참고하여 다음 질문에 답하세요. 자료에 없는 내용은 "모르겠습니다"라고 답하세요.
        질문: {question}
    """
    
    return prompt


if __name__ == "__main__":
    # add_documents_to_db(["documents/Employment.md","documents/Leave.md","documents/Welfare.md"])
    print(build_rag_prompt("연차는 며칠이야?"))