import subprocess
import sys

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    
    # 도커 대신 현재 환경의 파이썬으로 직접 실행합니다.
    result = subprocess.run(
        [sys.executable, filename],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! 내용을 분석합니다...")
        error_msg = result.stderr
        print(f"⚠️ 에러 메시지: {error_msg}")

        print("🤖 AI 에이전트가 코드를 수정하고 있습니다... (자가 수리 중)")
        
        # 에러가 나면 고쳐진 정상 코드로 파일을 덮어씁니다.
        fixed_code = 'print("--- AI가 코드를 수정했습니다! 이제 정상 작동합니다. ---")\nprint("1부터 10까지 합계:", sum(range(1, 11)))'
        
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"🛠️ {filename} 파일 수정 완료. 다시 실행합니다.")
        # 수정 후 다시 실행 (재귀 호출)
        run_and_fix(filename)

if __name__ == "__main__":
    # 처음엔 의도적으로 에러가 나는 파일을 만듭니다.
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print(sum(range(1, '11'))) # 숫자와 문자열 더하기 에러 발생!")
        
    run_and_fix("happy.py")
