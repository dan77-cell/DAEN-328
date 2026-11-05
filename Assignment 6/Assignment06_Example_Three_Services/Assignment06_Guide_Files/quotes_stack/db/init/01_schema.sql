CREATE TABLE IF NOT EXISTS authors (
    authorid   serial PRIMARY KEY,
    authorname varchar(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS quotes (
    quoteid  serial PRIMARY KEY,
    authorid integer NOT NULL REFERENCES authors (authorid),
    message  text NOT NULL UNIQUE,
    year     integer CHECK (year > 0)
);
