import logging

import psycopg2

from engine import loader
from engine.models import ngram, rnn
from engine.structure import Column

# This is the training set, also used for testing and giving a score estimate
# works as follows (RESOURCE_TYPE, TABLE.COLUMN, NB_DATASETS)
# More specifically, the NB_DATASETS is the nb of item columns from training of
# a given length (ex: 100) you want to extract from this real column. The idea
# being that for a huge column (>1M) I get extract 100 representative columns
# sampled by replacement.

source = [
    ("firstname", "firstnames.firstname", 100),
    ("name", "names.name", 100),
    ("code", "patients.gender", 10),
    ("code", "admissions.marital_status", 10),
    ("code", "admissions.religion", 10),
    ("code", "admissions.insurance", 10),
    ("code", "admissions.admission_location", 10),
    ("code", "prescriptions.drug_type", 30),
    ("code", "prescriptions.dose_unit_rx", 20),
    ("date", "prescriptions.startdate", 90),
    ("date", "admissions.admittime", 10),
    ("id", "admissions.hadm_id", 10),
    ("id", "admissions.subject_id", 10),
    ("id", "prescriptions.subject_id", 80),
    ("address", "addresses.road", 100),
    ("city", "addresses.city", 100),
]


def train(owner, database, model_type="ngram"):
    """
    Train a classification model on some dataset, and create a classification
    tool for columns of a given database, which will be used by the search
    engine. This database is intended to be different of the training database.
    :param owner: owner of the database
    :param database: database
    :param model: which model to use
    :return: the model train, with classification performed.
    """

    datasets, labels = spec_from_source(source)

    logging.warning("Fetching data...")
    columns = loader.fetch_columns(datasets, dataset_size=100)

    models = {"ngram": ngram.NGramClassifier, "rnn": rnn.RNNClassifier}
    model = models[model_type]()

    logging.warning("Preprocessing data...")
    X_train, y_train, X_test, y_test = model.preprocess(columns, labels)

    logging.warning("Fitting model...")
    model.fit(X_train, y_train)

    # Just to have an overview of the model performance on the training DB
    logging.warning("Score information:")
    y_pred = model.predict(X_test)
    model.score(y_pred, y_test)

    logging.warning("Building classification...")
    # Create connection to the `prod` database, on which we use the search engine
    sql_params = loader.get_sql_config("prod_database")
    with psycopg2.connect(**sql_params) as connection:
        # Get all tables
        prod_tables = loader.get_tables(connection)
        prod_table_columns = [
            "{}.{}".format(table, column)
            for table in prod_tables
            for column in loader.get_columns(table, connection)
        ]
        # Format to fit the transform and predict model pipeline
        # TODO: have a specific canal
        prod_source = [
            ("unknown", table_column, 1) for table_column in prod_table_columns
        ]
        prod_datasets, _labels = spec_from_source(prod_source)
        columns = loader.fetch_columns(prod_datasets, dataset_size=100)
        X, columns = model.preprocess(columns, _labels, test_only=True)
        # Keep the probabilities in the predictions, will be used for the scoring
        y_pred = model.predict_proba(X)

        # TODO : Move the classification elsewhere.
        classification = []
        for column, pred_proba in zip(columns, y_pred):
            column_name, column_data = column
            table_name = column_name.split(".")[0]
            column = Column(table_name, column_name, data=column_data)
            labels = [model.pred2label(input) for input in model.classes]
            proba_classes = {l: p for l, p in zip(labels, pred_proba)}
            column.set_proba_classes(proba_classes)
            classification.append(column)
        model.classification = classification

    logging.warning("Done. Ready!")
    return model


def spec_from_source(source):
    """
    Tool function to convert the user-friendly format of the source description to
    a format compatiable with the model pipeline
    :param source:
    :return:
    """
    datasets = []
    labels = []
    for column in source:
        if len(column) >= 3:
            label, column_name, nb_datasets = column
        else:
            label, column_name, nb_datasets = column[0], column[1], 1
        datasets.append((column_name, nb_datasets))
        labels += [label.upper()] * nb_datasets

    return datasets, labels
