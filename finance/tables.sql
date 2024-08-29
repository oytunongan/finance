CREATE TABLE transactions(
id INTEGER,
user_id INTEGER,
username TEXT,
cash NUMERIC,
stock TEXT,
stock_price FLOAT,
shares NUMERIC,
activity TEXT,
activity_date DATE,
PRIMARY KEY(id),
FOREIGN KEY(user_id) REFERENCES users(id)
);
