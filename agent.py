import subprocess
import sys
import os
import http.client
import json

# 🔒 GitHub Secrets에서 API 키를 가져옵니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini_to_fix(filename, error_msg):
    print("🤖 Gemini AI에게 수리를 요청하는 중...")
    
    if not GEMINI_API_KEY:
        print("❌ 에러: GEMINI_API_KEY 설정 확인 필요")
        sys.exit(1)

    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    prompt = f"다음 파이썬 코드의 에러를 수정해줘. 코드만 출력해.\n\n[에러]:\n{error_msg}\n\n[코드]:\n{code}"

    # 🔗 가장 안정적인 v1 경로 사용
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}
    
    # ⭐ 404 해결을 위한 최신 표준 엔드포인트
    endpoint = f"/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        conn.request("POST", endpoint, payload, headers)
        res = conn.getresponse()
        response_data = res.read().decode("utf-8")
        data = json.loads(response_data)

        if 'error' in data:
            print(f"❌ API 에러 발생: {data['error'].get('message')}")
            # 만약 v1에서 실패하면 v1beta로 마지막 재시도
            print("🔄 v1beta 경로로 마지막 재시도 중...")
            endpoint_beta = f"/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            conn.request("POST", endpoint_beta, payload, headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))

        # 최종 응답 추출
        if 'candidates' in data:
            fixed_code = data['candidates'][0]['content']['parts'][0]['text']
            # 마크다운 제거 루틴
            fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()
            return fixed_code
        else:
            print(f"⚠️ 응답 구조 오류: {data}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        sys.exit(1)

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI 분석 시작.")
        fixed_code = ask_gemini_to_fix(filename, result.stderr)
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"🛠️ {filename} 자가 수리 완료. 다시 실행합니다.")
        # 재시도 시 무한 루프 방지를 위해 한 번만 더 실행
        final_result = subprocess.run([sys.executable, filename], capture_output=True, text=True)
        if final_result.returncode == 0:
            print("✅ 수리 후 실행 성공! 결과:\n", final_result.stdout)
        else:
            print("❌ 수리 후에도 에러 발생:\n", final_result.stderr)

if __name__ == "__main__":
    # 에러가 확실히 발생하는 코드 생성
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print('결과는:', 10 / 0)")
    run_and_fix("happy.py")
