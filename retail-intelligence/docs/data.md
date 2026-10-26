# Source data

Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5CG6D

License: Creative Commons Attribution 4.0 International.
https://creativecommons.org/licenses/by/4.0/

The download script retrieves the original archive from UCI into data/raw. Raw data and the local database are excluded from this repository. The pipeline extracts it and builds the local database. data/raw/source.json records the original archive hash and retrieval timestamp. Do not edit source records; update cleaning rules in sql/clean.sql.
