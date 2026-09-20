# -*- coding: utf-8 -*-
r"""Gmail SMTP 첨부 메일 발송 스크립트 (앱 비밀번호 방식, 비밀번호는 Windows 자격 증명 관리자에 저장).

최초 1회 (주소·비밀번호는 본인이 직접 입력, 저장소에는 남지 않음):
    python C:\dev\tools\send_mail.py --setup
발송:
    python C:\dev\tools\send_mail.py --to a@b.com --subject "제목" --body "본문" --attach "C:\path\file.pptx"
    (--body-file 본문파일.txt / --attach 여러 번 가능 / --to 쉼표 구분)

주소는 소스가 아니라 ~/.send_mail.ini 에서 읽는다 (--setup 이 만들어 준다):
    [mail]
    from = me@gmail.com
    to = recipient@example.com
"""
import argparse, configparser, mimetypes, os, smtplib, sys
from email.message import EmailMessage

import keyring

SERVICE = "gmail-smtp"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".send_mail.ini")


def load_config():
    cp = configparser.ConfigParser()
    try:
        cp.read(CONFIG_PATH, encoding="utf-8")
    except configparser.Error as e:
        sys.exit(f"설정 파일을 읽을 수 없습니다: {CONFIG_PATH}\n  {e}")
    return dict(cp["mail"]) if cp.has_section("mail") else {}


def save_config(sender, to):
    cp = configparser.ConfigParser()
    cp.read(CONFIG_PATH, encoding="utf-8")
    if not cp.has_section("mail"):
        cp.add_section("mail")
    cp["mail"]["from"] = sender
    cp["mail"]["to"] = to
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        cp.write(f)
    print(f"설정 저장: {CONFIG_PATH}")


def setup():
    cfg = load_config()
    cur = cfg.get("from") or keyring.get_password(SERVICE, "__default_user__") or ""
    user = input(f"Gmail 주소{f' [{cur}]' if cur else ''}: ").strip() or cur
    if not user:
        sys.exit("Gmail 주소가 필요합니다.")
    pw = input("앱 비밀번호 16자리 (띄어쓰기 있어도 됨, 입력 글자 보임): ").replace(" ", "").strip()
    while len(pw) != 16:
        print(f"  -> {len(pw)}자리 입력됨. 16자리여야 합니다. 다시 입력하세요.")
        pw = input("앱 비밀번호 16자리: ").replace(" ", "").strip()
    keyring.set_password(SERVICE, user, pw)
    keyring.set_password(SERVICE, "__default_user__", user)
    print(f"저장 완료: {user} (Windows 자격 증명 관리자, 항목 '{SERVICE}')")
    cur_to = cfg.get("to", "")
    hint = f" [{cur_to}]" if cur_to else " (비워두면 발송 시 --to 필요)"
    to = input(f"기본 수신자{hint}: ").strip() or cur_to
    save_config(user, to)
    if input("테스트 메일을 본인에게 보낼까요? [y/N]: ").strip().lower() == "y":
        send(user, [user], "[send_mail.py] 테스트", "SMTP 설정 확인용 메일입니다.", [])


def send(user, to, subject, body, attachments):
    pw = keyring.get_password(SERVICE, user)
    if not pw:
        sys.exit(f"저장된 앱 비밀번호가 없습니다. 먼저 실행: python {__file__} --setup")
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        if not os.path.isfile(path):
            sys.exit(f"첨부 파일 없음: {path}")
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"발송 완료: {user} → {', '.join(to)} | {subject} | 첨부 {len(attachments)}개")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", action="store_true", help="주소·앱 비밀번호 저장(최초 1회)")
    ap.add_argument("--from-addr", default=None, help="생략 시 ~/.send_mail.ini 의 from")
    ap.add_argument("--to", default=None, help="쉼표로 여러 명. 생략 시 ~/.send_mail.ini 의 to")
    ap.add_argument("--subject", default="(제목 없음)")
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--attach", action="append", default=[])
    a = ap.parse_args()
    if a.setup:
        return setup()
    cfg = load_config()
    user = a.from_addr or cfg.get("from") or keyring.get_password(SERVICE, "__default_user__")
    if not user:
        sys.exit(f"보내는 주소가 없습니다. 먼저 실행: python {__file__} --setup")
    to = [t.strip() for t in (a.to or cfg.get("to", "")).split(",") if t.strip()]
    if not to:
        sys.exit(f"받는 주소가 없습니다. --to 로 지정하거나 {CONFIG_PATH} 의 [mail] to 를 설정하세요.")
    body = open(a.body_file, encoding="utf-8").read() if a.body_file else a.body
    send(user, to, a.subject, body, a.attach)


if __name__ == "__main__":
    main()
