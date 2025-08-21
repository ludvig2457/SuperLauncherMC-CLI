import os
import sys
import json
import subprocess
import shutil
import requests
from uuid import uuid1
from random_username.generate import generate_username
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command
from minecraft_launcher_lib.utils import get_minecraft_directory, get_version_list

CONFIG_FILE = "settings.json"
SERVERS_FILE = "servers_list.json"
SERVERS_DIR = "servers"
MODRINTH_API = "https://api.modrinth.com/v2"

minecraft_directory = get_minecraft_directory()
os.makedirs(minecraft_directory, exist_ok=True)
os.makedirs(SERVERS_DIR, exist_ok=True)
mods_dir = os.path.join(minecraft_directory, "mods")
os.makedirs(mods_dir, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"java_path": "", "ram": 4096}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def get_all_versions():
    versions = get_version_list()
    versions_dir = os.path.join(minecraft_directory, 'versions')
    if os.path.exists(versions_dir):
        for folder in os.listdir(versions_dir):
            if os.path.isdir(os.path.join(versions_dir, folder)) and not any(v['id']==folder for v in versions):
                versions.append({'id': folder})
    return versions

def show_versions():
    versions = get_all_versions()
    print("Доступные версии:")
    for i, v in enumerate(versions):
        print(f"{i}: {v['id']}")
    return versions

def launch_minecraft(version_id, username):
    if not username:
        username = generate_username()[0]
    options = {'username': username, 'uuid': str(uuid1()), 'token': ''}
    def progress(stage, value, max_value):
        print(f"{stage}: {value}/{max_value}" if max_value>0 else f"{stage}: {value}")
    print(f"Устанавливаем Minecraft {version_id}...")
    install_minecraft_version(version_id, minecraft_directory, callback={
        'setStatus': lambda v: progress("Статус", v, 0),
        'setProgress': lambda v: progress("Прогресс", v, 100),
        'setMax': lambda v: progress("Макс", v, v)
    })
    cmd = get_minecraft_command(version=version_id, minecraft_directory=minecraft_directory, options=options)
    print(f"Запуск Minecraft: {cmd}")
    subprocess.run(cmd, cwd=minecraft_directory)

def load_servers():
    if os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_servers(servers):
    with open(SERVERS_FILE, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

def download_server_jar(core, version, path):
    try:
        url = ""
        if core.lower() == "paper":
            data = requests.get(f"https://api.papermc.io/v2/projects/paper/versions/{version}").json()
            build = data["builds"][-1]
            url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{build}/downloads/paper-{version}-{build}.jar"
        elif core.lower() == "purpur":
            data = requests.get(f"https://api.purpurmc.org/v2/purpur/{version}").json()
            build = data["builds"][-1]
            url = f"https://api.purpurmc.org/v2/purpur/{version}/{build}/download"
        elif core.lower() == "vanilla":
            manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json").json()
            version_data = next(v for v in manifest["versions"] if v["id"]==version)
            version_json = requests.get(version_data["url"]).json()
            url = version_json["downloads"]["server"]["url"]
        else:
            print("Неподдерживаемое ядро")
            return False
        r = requests.get(url, stream=True)
        jar_path = os.path.join(path, "server.jar")
        with open(jar_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as e:
        print("Ошибка скачивания:", e)
        return False

def create_managed_server():
    name = input("Имя нового сервера: ").strip()
    port = input("Порт [25565]: ").strip() or "25565"
    version = input("Версия [1.20.4]: ").strip() or "1.20.4"
    core = input("Ядро [Paper/Purpur/Vanilla]: ").strip() or "Paper"
    path = os.path.join(SERVERS_DIR, name)
    os.makedirs(path, exist_ok=True)
    print("Скачиваем серверный JAR...")
    if not download_server_jar(core, version, path):
        print("Ошибка при скачивании сервера")
        return
    with open(os.path.join(path, "start.bat"), "w", encoding="utf-8") as f:
        f.write("@echo off\njava -Xmx2G -Xms2G -jar server.jar nogui\npause\n")
    with open(os.path.join(path, "eula.txt"), "w", encoding="utf-8") as f:
        f.write("eula=false\n")
    with open(os.path.join(path, "server.properties"), "w", encoding="utf-8") as f:
        f.write(f"server-port={port}\nonline-mode=true\n")
    servers = load_servers()
    servers.append({"name": name, "ip": f"localhost:{port}", "managed": True, "version": version, "core": core})
    save_servers(servers)
    print(f"Сервер {name} создан!")

def list_servers():
    servers = load_servers()
    if not servers:
        print("Серверов нет")
        return
    for i, s in enumerate(servers):
        managed = " (управляемый)" if s.get("managed") else ""
        print(f"{i}: {s['name']} - {s['ip']}{managed}")

def manage_server():
    servers = load_servers()
    list_servers()
    if not servers: return
    idx = int(input("Выберите сервер: "))
    server = servers[idx]
    if not server.get("managed"):
        print("Сервер не управляется локально")
        return
    path = os.path.join(SERVERS_DIR, server["name"])
    while True:
        print(f"\nУправление сервером '{server['name']}'")
        print("1: EULA True/False")
        print("2: Онлайн/Оффлайн режим")
        print("3: Запустить сервер")
        print("4: Остановить сервер (через диспетчер задач)")
        print("0: Назад")
        choice = input("> ").strip()
        if choice=="1":
            eula_file = os.path.join(path, "eula.txt")
            with open(eula_file,"r") as f:
                val=f.read().strip().lower()
            new_val="true" if "false" in val else "false"
            with open(eula_file,"w") as f:
                f.write(f"eula={new_val}\n")
            print(f"EULA={new_val}")
        elif choice=="2":
            prop_file = os.path.join(path, "server.properties")
            props = {}
            if os.path.exists(prop_file):
                with open(prop_file,"r") as f:
                    for line in f:
                        if "=" in line: k,v=line.strip().split("=",1); props[k]=v
            current = props.get("online-mode","true")
            props["online-mode"]="false" if current=="true" else "true"
            with open(prop_file,"w") as f:
                for k,v in props.items(): f.write(f"{k}={v}\n")
            print(f"online-mode={props['online-mode']}")
        elif choice=="3":
            bat_path=os.path.join(path,"start.bat")
            if os.path.exists(bat_path):
                subprocess.Popen(["cmd.exe","/k","start.bat"],cwd=path)
            else:
                print("start.bat не найден")
        elif choice=="4":
            print("Остановите сервер вручную через диспетчер задач")
        elif choice=="0": break

def delete_server():
    servers = load_servers()
    list_servers()
    if not servers: return
    idx = int(input("Выберите сервер для удаления: "))
    server = servers.pop(idx)
    if server.get("managed"):
        shutil.rmtree(os.path.join(SERVERS_DIR, server["name"]), ignore_errors=True)
    save_servers(servers)
    print(f"Сервер {server['name']} удалён")

def list_featured_mods():
    try:
        url = f"{MODRINTH_API}/search?limit=10&index=relevance"
        resp = requests.get(url).json()
        print("\nПопулярные моды Modrinth:")
        for i, hit in enumerate(resp["hits"], 1):
            print(f"{i}. {hit['title']} — {hit.get('description','')[:60]}...")
        return resp["hits"]
    except Exception as e:
        print("Ошибка загрузки модов:", e)
        return []

def search_mods(query):
    try:
        url = f"{MODRINTH_API}/search?query={query}&limit=10"
        resp = requests.get(url).json()
        results = resp["hits"]
        if not results:
            print("Моды не найдены")
            return []
        print(f"\nРезультаты поиска '{query}':")
        for i, hit in enumerate(results,1):
            print(f"{i}. {hit['title']} — {hit.get('description','')[:60]}...")
        return results
    except Exception as e:
        print("Ошибка поиска:", e)
        return []

def download_mod(project_id):
    try:
        versions_url = f"{MODRINTH_API}/project/{project_id}/version"
        versions = requests.get(versions_url).json()
        for v in versions:
            for f in v["files"]:
                if f["filename"].endswith(".jar"):
                    url = f["url"]
                    filename = f["filename"]
                    save_path = os.path.join(mods_dir, filename)
                    print(f"Скачиваем {filename}...")
                    with requests.get(url, stream=True) as r, open(save_path, "wb") as out:
                        total = int(r.headers.get("content-length",0))
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=8192):
                            out.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                percent = int(downloaded*100/total)
                                print(f"\r{percent}% загружено", end="")
                    print("\nГотово!")
                    return
        print("Подходящий .jar файл не найден")
    except Exception as e:
        print("Ошибка загрузки:", e)

def open_mods_folder():
    path = os.path.realpath(mods_dir)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        os.system(f"open \"{path}\"")
    else:
        os.system(f"xdg-open \"{path}\"")

def delete_all_mods():
    confirm = input("Удалить все моды? (y/N): ").lower()
    if confirm != "y":
        return
    deleted = 0
    for file in os.listdir(mods_dir):
        if file.endswith(".jar"):
            try:
                os.remove(os.path.join(mods_dir, file))
                deleted += 1
            except:
                pass
    print(f"Удалено модов: {deleted}")

def mods_cli_menu():
    last_mods_list = []
    while True:
        print("\nМеню модов:")
        print("1. Популярные моды")
        print("2. Поиск мода")
        print("3. Скачать мод по номеру из списка")
        print("4. Открыть папку модов")
        print("5. Удалить все моды")
        print("0. Назад")
        choice = input("> ").strip()
        if choice=="1":
            last_mods_list = list_featured_mods()
        elif choice=="2":
            query = input("Поиск: ")
            last_mods_list = search_mods(query)
        elif choice=="3":
            if not last_mods_list:
                print("Сначала покажите или найдите моды")
                continue
            idx = int(input(f"Выберите номер (1-{len(last_mods_list)}): ")) - 1
            if 0 <= idx < len(last_mods_list):
                download_mod(last_mods_list[idx]["project_id"])
            else:
                print("Неверный номер")
        elif choice=="4":
            open_mods_folder()
        elif choice=="5":
            delete_all_mods()
        elif choice=="0":
            break
        else:
            print("Неверный выбор!")

def show_news():
    news_list = [
        ("2025-07-12", "Добавлен новый сервер в мультиплеер"),
        ("2025-07-10", "Добавлена новая версия Minecraft 1.20.1"),
        ("2025-07-05", "Исправлены ошибки при запуске игры"),
    ]
    print("\nНовости SuperLauncher:")
    for date, text in news_list:
        print(f"{date}: {text}")

def main():
    config = load_config()
    while True:
        print("\nSuperLauncher CLI")
        print("1: Список версий")
        print("2: Запустить версию")
        print("3: Настройки")
        print("4: Список серверов")
        print("5: Создать управляемый сервер")
        print("6: Управление сервером")
        print("7: Удалить сервер")
        print("8: Моды")
        print("9: Новости")
        print("0: Выход")
        choice = input("> ").strip()
        if choice=="1": show_versions()
        elif choice=="2":
            versions = show_versions()
            idx = int(input("Выберите номер версии: "))
            username = input("Имя игрока (Enter для случайного): ")
            launch_minecraft(versions[idx]["id"], username)
        elif choice=="3":
            print(f"Текущие настройки: {config}")
            ram = input("RAM (MB): ").strip()
            java_path = input("Путь к Java: ").strip()
            if ram: config["ram"]=int(ram)
            if java_path: config["java_path"]=java_path
            save_config(config)
        elif choice=="4":
            list_servers()
        elif choice=="5":
            create_managed_server()
        elif choice=="6":
            manage_server()
        elif choice=="7":
            delete_server()
        elif choice=="8":
            mods_cli_menu()
        elif choice=="9":
            show_news()
        elif choice=="0":
            break
        else:
            print("Неверный выбор")

if __name__ == "__main__":
    main()
