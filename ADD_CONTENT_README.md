# Adding content to the South-View database

This tool adds to the website's information through simple questions in a terminal. You don't need to know any code. Nothing is saved unless you type `yes`.

## How to run it

1. Open a terminal in the project folder.
2. Type `python add_content.py` and press Enter. If you see "command not found", type `python3 add_content.py` instead.
3. Type the number of what you want to do. Type `q` at any question to leave, or leave a question blank to go back.

For longer text, type or paste it, then type `DONE` on its own line and press Enter.

## What each option does

1. **New profile section:** adds a section to a prominent figure's profile.
2. **Timeline event:** adds a dated event to a prominent figure's timeline.
3. **Source link:** adds a source to the end of a prominent figure's list.
4. **FAQ:** adds a question and answer. It warns you if a similar question exists.
5. **New person:** adds someone to the directory.
6. **Update biography:** replaces a person's biography. It shows you the before and after.
7. **Check for problems:** looks over the database and changes nothing.

## Rules

- **Write in your own words.** Do not paste text from the book, from articles or from websites.
- **Every addition needs a source** with a title, a web address and a publisher.

## After you save

1. Upload/commit `southview_rag_database.json` to GitHub (ask the maintainer if you don't have access).
2. Ask the app owner to Reboot the app at share.streamlit.io.
3. Search for the person on the live site to confirm.

## If something goes wrong

- **The tool says it restored the backup:** your change was not saved and the database is back to how it was. Send the maintainer the message on screen.
- **You saved a mistake:** run the tool again to correct it. For a biography, use option 6. For anything else, ask the maintainer, who can use the dated copies in the `backups` folder.
- **Any other error:** try once more. If it happens again, send the maintainer `backups/last_error.txt`.
