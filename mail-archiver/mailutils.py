from email.header import decode_header
from email.utils import parsedate
from email.parser import Parser
from email.policy import default
import imaplib
import mailbox
import re
import sys
import time
from tinydb import TinyDB, Query


from .utils import normalize, slugify_safe, detect_encoding

def extract_date(email):
    date = email.get('Date')
    return parsedate(date)

def imap_connect( IMAP_SERVER, IMAP_USERNAME, IMAP_PASSWORD, IMAP_SSL):
    """
    Connect to remote server
    """
    if IMAP_SSL is True:
        connection = imaplib.IMAP4_SSL(IMAP_SERVER)
    else:
        connection = imaplib.IMAP4(IMAP_SERVER)
    if IMAP_SSL == 'starttls':
        mail.starttls()
    connection.login(IMAP_USERNAME, IMAP_PASSWORD)

    try:
        connection.enable("UTF8=ACCEPT")
    except Exception as e:
        print("Server does not accept UTF8=ACCEPT")

    return connection

def get_mail_folders(settings, connection = None, mail_folders = None):
    """
    Returns mail folders
    """

    if not mail_folders is None:
        return mail_folders

    if not mail:
        return mail_folders

    mail_folders = {}
    maillist, folder_separator = get_all_folders(connection)
    count = 0
    to_exclude = settings.get('excluded_folders',[])
    for folder_id in maillist:
        if folder_id not in to_exclude:
            # print(folder_id)
            count += 1

            # TODO, if separator is part of the name, multiple levels arise (that do not exist)
            parts = folder_id.split(folder_separator)

            fileName = "%03d-%s.html" % (count, slugify_safe(normalize(folder_id, "utf7"), defaultVal="folder"))

            isSelected = False
            for selected_folder in settings.get('folders'):
                if re.search("^" + selected_folder + "$", folder_id):
                    isSelected = True
                    break

            mail_folders[folder_id] = {
                "id": folder_id,
                "title": normalize(parts[len(parts) - 1], "utf7"),
                "parent": folder_separator.join(parts[:-1]),
                "selected": '--all' in settings.get('folders') or isSelected,
                "file": fileName,
                "link": "/%s" % fileName,
            }

    # Single root folders do not matter really - usually it's just "INBOX"
    # Let's see how many menus exist with no parent
    menusWithNoParent = []
    for menu in mail_folders:
        if mail_folders[menu]["parent"] == "":
            menusWithNoParent.append(menu)

    # None found or more than one, go home
    if len(menusWithNoParent) == 1:
        # We remove it - Why???
        # del mail_folders[menusWithNoParent[0]]

        # We change fatherhood for all children
        for menu in mail_folders:
            if mail_folders[menu]["parent"] == menusWithNoParent[0]:
                mail_folders[menu]["parent"] = ""
    # print(mail_folders)
    return mail_folders

def get_all_folders(connection):
    """
    Returns all folders from remote server
    """
    folder_list = []
    folder_separator = None
    maillist = connection.list()
    if not maillist or not maillist[0].lower() == 'ok':
        print("Unable to retrieve folder list")

        return folder_list, folder_separator
    for folder_line in maillist[1]:
        folder_line = folder_line.decode()
        parts = re.findall("(\(.*\)) \"(.)\" (.*)", folder_line)    
        if not parts:
            print("Unable to decode filder structure: %s" % folder_line)
            continue

        folder_list.append(parts[0][2].strip().strip('"'))

        if not folder_separator:
            folder_separator = parts[0][1]

    return folder_list, folder_separator


def saveToMaildir(msg, mail_folder, maildir_raw):
    """
    Saves a single email to local clone
    """
    mbox = mailbox.Maildir(maildir_raw, factory=mailbox.MaildirMessage, create=True) 
    folder = mbox.add_folder(mail_folder)
    folder.lock()
    try:
        message_key = folder.add(msg)
        folder.flush()

        maildir_message = folder.get_message(message_key)
        try:
            message_date_epoch = time.mktime(parsedate(decode_header(maildir_message.get("Date"))[0][0]))
        except TypeError as typeerror:
            message_date_epoch = time.mktime((2000, 1, 1, 1, 1, 1, 1, 1, 0))
        maildir_message.set_date(message_date_epoch)
        maildir_message.add_flag("s")

    finally:
        folder.unlock()
        folder.close()
        mbox.close()

def get_message_to_local(mail_folder, connection, settings):
    """
    Goes over a folder and save all emails
    """
    maildir_raw = settings['maildir_raw']
    db =  TinyDB(settings['db'])
    print("Selecting folder %s" % normalize(mail_folder, "utf7"), end="")
    connection.select(connection._quote(mail_folder), readonly=True)
    print("..Done!")

    try:
        typ, mdata = connection.search(None, "ALL")
    except Exception as imaperror:
        print("Error in IMAP Query: %s." % imaperror)
        print("Does the imap folder \"%s\" exists?" % mail_folder)
        return

    message_list = mdata[0].decode().split()
    sofar = 0
    print("Copying folder %s (%s)" % (normalize(mail_folder, "utf7"), len(message_list)), end="")
    Msg = Query()
    for message_id in message_list:
        result, data = connection.fetch(message_id , "(RFC822)")
        raw_email = data[0][1].replace(b'\r\n', b'\n')
        maildir_folder = mail_folder.replace("/", ".")
        encoding = detect_encoding(raw_email)
        try:
            headers = Parser(policy=default).parsestr( raw_email.decode(encoding) )
            # mmm = mailbox.MaildirMessage(message=raw_email)
            message_id = headers['Message-ID']
            # print(message_id)
            find = db.search((Msg.message_id == message_id) & (Msg.mail_folder == mail_folder))
            if len(find) == 0:
                subject = headers['Subject']
                if '* SPAM *' not in subject:
                    print("To download")
                    db.insert({'message_id': message_id, 'mail_folder': mail_folder})
                    saveToMaildir(raw_econnection, maildir_folder, maildir_raw)
                else:
                    print("Subject contains spam")
            else:
                print("Already exists")
                
        except:
            # print(raw_email)
            pass
        sofar += 1

        if sofar % 10 == 0:
            print(sofar, end="")
        else:
            print('.', end="")
        sys.stdout.flush()
    
    print("..Done!")
