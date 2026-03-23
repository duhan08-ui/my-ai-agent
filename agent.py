import subprocess
import os

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    
    # 1. 도커 컨테이너를 이용해 코드 실행 (결과물 캡처)
    # --rm 옵션으로 실행 후 찌꺼기 제거, 현재 폴더 마운트
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{os.getcwd()}:/app", "-w", "/app", "python:3.9-slim", "python", filename],
        capture_output=True, text=True
    )

    # 2. 결과 확인
    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! 내용을 분석합니다...")
        error_msg = result.stderr
        print(f"⚠️ 에러 메시지: {error_msg}")

        # 3. [데빈의 핵심] AI에게 수정을 요청하는 부분 (가상 구현)
        print("🤖 AI 에이전트가 코드를 수정하고 있습니다... (자가 수리 중)")
        
        # 실제로는 여기서 OpenAI API 등에 에러 메시지를 보내 수정한 코드를 받아옵니다.
        # 여기서는 예시로 '에러가 없는 정상 코드'로 파일을 덮어쓰겠습니다.
        fixed_code = 'print("--- AI가 코드를 수정했습니다! 이제 정상 작동합니다. ---")\nprint("1부터 10까지 합계:", sum(range(1, 11)))'
        
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"🛠️ {filename} 파일 수정 완료. 다시 실행합니다.")
        run_and_fix(filename) # 재귀적으로 다시 실행

if __name__ == "__main__":
    # 처음엔 에러가 나는 파일을 준비합니다.
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print(sum(range(1, '11'))) # 의도적인 에러: 숫자와 문자열 더하기")
        
    run_and_fix("happy.py")