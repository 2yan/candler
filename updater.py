import os
import datetime

time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

os.system('git pull')
os.system('git add fire.db')
os.system("git commit -m'Data: {}'".format(time))
os.system('git push')



