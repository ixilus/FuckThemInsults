

__author__ = 'tpc 2015'

import json

from sklearn.linear_model import SGDClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn import cross_validation
from sklearn.grid_search import GridSearchCV

class InsultDetector:
    def __init__(self):
        pass

    def _json_to_dataset(self, json_data):
        dataset = dict(data=1, target=2)
        dataset['data'] = []
        dataset['target'] = []

        def _iterate(json_data):
            if 'text' in json_data and 'insult' in json_data and json_data['text']:
                dataset['data'].append(json_data['text'])
                dataset['target'].append(json_data['insult'])
            if 'children' in json_data:
                for child in json_data['children']:
                    _iterate(child)

        for root in json_data:
            _iterate(root["root"])

        return dataset

    def train(self, labeled_discussions):
        if (type(labeled_discussions) is list): # for cross validation
            dataset = self._json_to_dataset(labeled_discussions)
        else:
            dataset = labeled_discussions

        text_clf = Pipeline([('vect',  TfidfVectorizer(max_df=0.75, ngram_range=(1, 2))),
                             ('clf',   SGDClassifier(class_weight='auto',
                                                     n_jobs=-1,
                                                     alpha=5e-06,
                                                     loss='squared_hinge',
                                                     n_iter=10))])

        self.text_clf = text_clf.fit(dataset['data'], dataset['target'])

    def classify(self, unlabeled_discussions):
        def _iterate(discussion):
            if 'text' in discussion and not discussion['text']:
                discussion['insult'] = False
            elif 'text' in discussion:
                discussion['insult'] = self.text_clf.predict([discussion['text']])[0]
            if 'children' in discussion:
                for child in discussion['children']:
                    _iterate(child)

        if type(unlabeled_discussions[0]) is dict: # for easier cross validation
            for root in unlabeled_discussions:
                _iterate(root["root"])
        else:
            return self.text_clf.predict(unlabeled_discussions)
        return unlabeled_discussions

    def _grid_search(self, json_data):
        dataset = self._json_to_dataset(json_data)
        # text_clf = Pipeline([('vect',  TfidfVectorizer()),
        #                      ('clf',   SGDClassifier(class_weight='auto', n_jobs=-1))])
        text_clf = Pipeline([('vect',  TfidfVectorizer(max_df=0.75, ngram_range=(1, 2))),
                             ('clf',   SGDClassifier(class_weight='auto',
                                                     n_jobs=-1,
                                                     loss='squared_hinge',
                                                     n_iter=5))])
        parameters = {
                        'clf__alpha': (678e-8, 679e-8, 680e-8),
                      # 'clf__loss': ('hinge', 'squared_hinge', 'modified_huber', 'squared_loss'),
                      # 'clf__n_iter': (5, 10, 20),
                      # 'clf__penalty': ('l2', 'elasticnet'),
                      # 'vect__max_df': (0.5, 0.75, 1.0),
                      # 'vect__ngram_range': [(1, 1), (1, 2)]
                      }
        gs_clf = GridSearchCV(text_clf, parameters, n_jobs=-1, scoring='f1')
        gs_clf = gs_clf.fit(dataset['data'], dataset['target'])
        best_parameters, score, _ = max(gs_clf.grid_scores_, key=lambda x: x[1])
        for param_name in sorted(parameters.keys()):
            print("%s: %.10f" % (param_name, best_parameters[param_name]))
        print(score)

    def _cross_validate(self, json_data):
        dataset = self._json_to_dataset(json_data)
        text_clf = Pipeline([('vect',  TfidfVectorizer(max_df=0.75, ngram_range=(1, 2))),
                             ('clf',   SGDClassifier(class_weight='auto',
                                                     n_jobs=-1,
                                                     alpha=5e-6,
                                                     loss='squared_hinge',
                                                     n_iter=10))])
        score = cross_validation.cross_val_score(text_clf, dataset['data'], dataset['target'], cv=5, scoring='f1')
        print(score)

    def test(self):
        json_file = open('discussions.json', encoding='utf-8', errors='replace')
        # json_file = open('test_discussions/learn.json')
        json_data = json.load(json_file)

        self._cross_validate(json_data)
        # self._grid_search(json_data)

    def _test_if_i_broke_something(self):
        # json_file = open('discussions.json', encoding='utf-8', errors='replace')
        json_file = open('test_discussions/learn.json')
        json_data = json.load(json_file)
        self.train(json_data)
        json_test = open('test_discussions/test.json')
        json_test_data = json.load(json_test)
        print(self.classify(json_test_data))

if __name__ == '__main__':
    d = InsultDetector()
    d.test()
    # d._test_if_i_broke_something()