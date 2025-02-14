from email.header import decode_header
from email.utils import parsedate
import imaplib
import mailbox
import re
import sys
import time

from .utils import normalize, slugify_safe

def extract_date(email):
    date = email.get('Date')
    return parsedate(date)

def connectToImapMailbox( IMAP_SERVER, IMAP_USERNAME, IMAP_PASSWORD, IMAP_SSL):
    """
    Connects to remote server
    """
    if IMAP_SSL is True:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    else:
        mail = imaplib.IMAP4(IMAP_SERVER)
    if IMAP_SSL == 'starttls':
        mail.starttls()
    print(IMAP_SERVER)
    print(IMAP_USERNAME)
    print(IMAP_PASSWORD)
    mail.login(IMAP_USERNAME, IMAP_PASSWORD)

    try:
        mail.enable("UTF8=ACCEPT")
    except Exception as e:
        print("Server does not accept UTF8=ACCEPT")

    return mail

def getMailFolders(settings, mail = None, mailFolders = None):
    """
    Returns mail folders
    """
    # global mailFolders
    # global server

    if not mailFolders is None:
        return mailFolders

    if not mail:
        return mailFolders

    mailFolders = {}
    maillist, folderSeparator = getAllFolders(mail)
    count = 0
    to_exclude = settings.get('excluded_folders',[])
    for folder_id in maillist:
        if folder_id not in to_exclude:
            count += 1

            # TODO, if separator is part of the name, multiple levels arise (that do not exist)
            parts = folder_id.split(folderSeparator)

            fileName = "%03d-%s.html" % (count, slugify_safe(normalize(folder_id, "utf7"), defaultVal="folder"))

            isSelected = False
            for selected_folder in settings.get('folders'):
                if re.search("^" + selected_folder + "$", folder_id):
                    isSelected = True
                    break

            mailFolders[folder_id] = {
                "id": folder_id,
                "title": normalize(parts[len(parts) - 1], "utf7"),
                "parent": folderSeparator.join(parts[:-1]),
                "selected": '--all' in settings.get('folders') or isSelected,
                "file": fileName,
                "link": "/%s" % fileName,
            }

    # Single root folders do not matter really - usually it's just "INBOX"
    # Let's see how many menus exist with no parent
    menusWithNoParent = []
    for menu in mailFolders:
        if mailFolders[menu]["parent"] == "":
            menusWithNoParent.append(menu)

    # None found or more than one, go home
    if len(menusWithNoParent) == 1:
        # We remove it
        del mailFolders[menusWithNoParent[0]]

        # We change fatherhood for all children
        for menu in mailFolders:
            if mailFolders[menu]["parent"] == menusWithNoParent[0]:
                mailFolders[menu]["parent"] = ""

    return mailFolders

def getAllFolders(mail):
    """
    Returns all folders from remote server
    """
    folderList = []
    folderSeparator = ''

    maillist = mail.list()
    if not maillist or not maillist[0].lower() == 'ok':
        print("Unable to retrieve folder list")
        return folderList, folderSeparator

    for folderLine in maillist[1]:
        folderLine = folderLine.decode()
        parts = re.findall("(\(.*\)) \"(.)\" (.*)", folderLine)

        if not parts:
            print("Unable to decode filder structure: %s" % folderLine)
            continue

        folderList.append(parts[0][2].strip().strip('"'))

        if not folderSeparator:
            folderSeparator = parts[0][1]

    return folderList, folderSeparator


def saveToMaildir(msg, mailFolder, maildir_raw):
    """
    Saves a single email to local clone
    """
    mbox = mailbox.Maildir(maildir_raw, factory=mailbox.MaildirMessage, create=True) 
    folder = mbox.add_folder(mailFolder)    
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


def get_message_to_local(mailFolder, mail, maildir_raw):
    """
    Goes over a folder and save all emails
    """
    print("Selecting folder %s" % normalize(mailFolder, "utf7"), end="")
    mail.select(mail._quote(mailFolder), readonly=True)
    print("..Done!")

    try:
        typ, mdata = mail.search(None, "ALL")
    except Exception as imaperror:
        print("Error in IMAP Query: %s." % imaperror)
        print("Does the imap folder \"%s\" exists?" % mailFolder)
        return

    messageList = mdata[0].decode().split()
    sofar = 0
    print("Copying folder %s (%s)" % (normalize(mailFolder, "utf7"), len(messageList)), end="")
    for message_id in messageList:
        result, data = mail.fetch(message_id , "(RFC822)")
        raw_email = data[0][1].replace(b'\r\n', b'\n')
        maildir_folder = mailFolder.replace("/", ".")
        # print(maildir_folder)
        # print(maildir_raw)
        saveToMaildir(raw_email, maildir_folder, maildir_raw)
        sofar += 1

        if sofar % 10 == 0:
            print(sofar, end="")
        else:
            print('.', end="")
        sys.stdout.flush()
    
    print("..Done!")
