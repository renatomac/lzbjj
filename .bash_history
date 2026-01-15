cd
python manage.py migrate
python manage.py check
python manage.py makemigrations
python manage.py migrate
ls
git pull origin main
ls
git clone git@github.com:renatomac/lzbjj.git .
git init
git remote add origin git@github.com:renatomac/lzbjj.git
git remote -v
git add .
git commit -m "Initial Django project"
git config --global user.name "Jorge Renato Macedo"
git config --global user.email "renato.2208@.com"
git config --global --list
git add .
git commit -m "Initial Django project"
git push -u origin main
git branch -m master main
git push -u origin main   
ls ~/.ssh/id_rsa.pub
ls ~/.ssh/id_ed25519.pub
ssh-keygen -t ed25519 -C "renato.2208@gmail.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
ssh -T git@github.com
git pull origin main
git pull origin main --no-rebase
git config pull.rebase false
git pull origin main
git pull origin main --rebase
git status
git add .gitignore
git commit -m "Update .gitignore to ignore virtualenv and SSH keys"
git pull origin main --allow-unrelated-histories
git status
git checkout --theirs .
git commit
git add .
git commit -m "Merged remote main into local, keeping remote versions"
git status
git push origin main
git pull origin main
exit
