import os
import glob

def get_latest_log_file():
    log_dir = os.path.join(os.getcwd(), "logs")
    log_files = glob.glob(os.path.join(log_dir, "*.log")) + glob.glob(os.path.join(log_dir, "*.json"))
    if not log_files:
        return None
    return max(log_files, key=os.path.getmtime)

def main():
    print("=== DUMP DE LOGS DA VPS ===")
    latest = get_latest_log_file()
    if not latest:
        print("Nenhum arquivo de log encontrado na pasta logs/.")
        return
        
    print(f"Lendo o arquivo: {latest}\n")
    with open(latest, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        
    for line in lines[-100:]:
        print(line.strip())

if __name__ == "__main__":
    main()
