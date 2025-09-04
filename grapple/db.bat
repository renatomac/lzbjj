cd grapple
del migrations
del grapple_dev.db
flask db init
flask db migrate
flask db upgrade