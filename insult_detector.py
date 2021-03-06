# -*- coding: utf-8 -*-
import json
import re
import numpy as np
import matplotlib.pyplot as plt
from scipy import sparse
import time

from sklearn.linear_model import SGDClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn import cross_validation
from sklearn.grid_search import GridSearchCV
from sklearn.base import TransformerMixin
from sklearn.metrics import f1_score
from sklearn.svm.classes import LinearSVC
from sklearn.svm.classes import SVC
from sklearn.preprocessing import StandardScaler

import random

__author__ = 'tpc 2015'

word_regexp = re.compile(u"(?u)\w+|:\)+|;\)+|:\-\)+|;\-\)+|%\)|=\)+|\(\(+|\)\)+|!+|\?|\+[0-9]+|\++")

def my_tokenizer(text, stop_words=None):
    tokens = word_regexp.findall(text.lower())
    filtered_tokens = []
    for token in tokens:
        ch = token[0]
        if stop_words is not None and token in stop_words:
            continue
        if ch == ':' or ch == ';' or ch == '=' or ch == '%':
            token = ':)'
        elif ch == '(':
            token = '('
        elif ch == ')':
            token = ')'
        elif ch == '?':
            token = '?'
        elif ch == '!':
            token = '!'
        elif ch == '+':
            token = '+'
        elif '0' <= ch <= '9':
            continue
        filtered_tokens.append(token)
    return filtered_tokens


class DenseTransformer(TransformerMixin):
    def transform(self, x, y=None, **fit_params):
        print(x.shape)
        return x.toarray()

    def fit(self, X, y=None, **fit_params):
        return self


class InsultFeatures(TransformerMixin):
    def __init__(self, insult_words_regex, address_words_regex, weak_insult_words_regex):
        self.insult_words_regex = insult_words_regex
        self.address_words_regex = address_words_regex
        self.weak_insult_words_regex = weak_insult_words_regex

    def transform(self, texts):
        features = []

        positive_texts = 0

        # Some advanced level text processing!
        for text in texts:
            this_features = []
            tokens = my_tokenizer(text)

            insult_range = 0
            address_range = 0
            weak_insult_range = 0

            directed_insults = 0
            total_insults = 0
            token_count = 0

            was_insult = 0

            pattern = []

            for token in tokens:
                is_address = False
                is_insult = False
                is_weak_insult = False

                pattern.append(token)
                if self.address_words_regex.match(token):
                    is_address = True
                elif self.insult_words_regex.match(token):
                    is_insult = True
                elif self.weak_insult_words_regex.match(token):
                    is_weak_insult = True

                # Just insults, not super accurate..
                if is_insult or (address_range > 0 or insult_range > 0) and is_weak_insult:
                    total_insults += 1
                    was_insult = 1

                # More direct insults
                if \
                        insult_range > 0 and (is_insult or is_address or is_weak_insult) \
                        or address_range > 0 and (is_insult or is_weak_insult) \
                        or weak_insult_range > 0 and (is_insult or is_address):
                    directed_insults += 1
                    # print(pattern)

                insult_range -= 1
                address_range -= 1
                weak_insult_range -= 1

                if is_insult:
                    insult_range = 3
                elif is_address:
                    address_range = 3
                elif is_weak_insult:
                    weak_insult_range = 2

                token_count += 1
                if len(pattern) > 3:
                    pattern = pattern[1:]

            if len(tokens) == 0:
                insults_ratio = 0
            else:
                insults_ratio = total_insults / len(tokens)

            if directed_insults > 2:
                directed_insults = 1
            else:
                directed_insults /= 2

            positive_texts += was_insult
            this_features.append(directed_insults)
            this_features.append(len(text))
            # this_features.append(total_insults)
            this_features.append(insults_ratio)

            features.append(this_features)

        print(positive_texts, positive_texts / len(texts))
        return sparse.csr_matrix(features)

    def fit(self, texts, y=None):
        return self

    def get_params(self, deep=True):
        return {}

    def set_params(self, **parameters):
        for parameter, value in parameters.items():
            pass
        return self


class InsultDetector:
    def __init__(self):
        with open('insult_words.txt', mode='r', encoding='utf-8') as file:
            insult_words = file.read().splitlines()
        with open('address_words.txt', mode='r', encoding='utf-8') as file:
            address_words = file.read().splitlines()
        with open('weak_insults.txt', mode='r', encoding='utf-8') as file:
            weak_insult_words = file.read().splitlines()
        with open('stop_words.txt', mode='r', encoding='utf-8') as f:
            self.stop_words = f.read().splitlines()

        self.text_clf = None
        self.insult_words_regex = self.create_regex(insult_words)
        self.address_words_regex = self.create_regex(address_words)
        self.weak_insult_words_regex = self.create_regex(weak_insult_words)

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

    @staticmethod
    def create_regex(expression_list):
        regex_str = '^('
        for exp in expression_list:
            regex_str += exp + '|'
        regex_str = regex_str[:-1] + ')$'
        regex = re.compile(regex_str)
        return regex

    @staticmethod
    def _reduce_dataset(dataset):
        set_length = len(dataset['data'])
        num_insults = 0

        reduced_dataset = dict(data=1, target=2)
        reduced_dataset['data'] = []
        reduced_dataset['target'] = []

        for i in range(set_length):
            if dataset['target'][i]:
                num_insults += 1
                reduced_dataset['data'].append(dataset['data'][i])
                reduced_dataset['target'].append(True)
        step = set_length / num_insults / 4

        for i in range(0, set_length,  round(step)):
            if not dataset['target'][i]:
                reduced_dataset['data'].append(dataset['data'][i])
                reduced_dataset['target'].append(False)

        print(len(reduced_dataset['data']), num_insults)
        return reduced_dataset

    def train(self, labeled_discussions):
        if type(labeled_discussions) is list:  # for cross validation
            dataset = self._json_to_dataset(labeled_discussions)
        else:
            dataset = labeled_discussions
        # dataset = self._reduce_dataset(dataset)

        text_clf = Pipeline([
            ('vect', FeatureUnion(
                transformer_list=[
                    ('tfidf', TfidfVectorizer(ngram_range=(1, 2),
                                              tokenizer=my_tokenizer,
                                              stop_words=self.stop_words)),
                    ('insults', InsultFeatures(self.insult_words_regex,
                                               self.address_words_regex,
                                               self.weak_insult_words_regex))
                ],
                transformer_weights={
                    'tfidf': 0.4,   # 3 2 4 4+len
                    'insults': 1.0
                })),
            # ('todense', DenseTransformer()),
            ('scaler', StandardScaler(with_mean=False)),
            ('clf', SVC(verbose=True, class_weight='auto', kernel='rbf', C=240, max_iter=10000, gamma=3e-8))
        ])

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

        if type(unlabeled_discussions[0]) is dict:  # for easier cross validation
            for root in unlabeled_discussions:
                _iterate(root["root"])
        else:
            return self.text_clf.predict(unlabeled_discussions)
        return unlabeled_discussions

    def _grid_search(self, json_data):
        dataset = self._json_to_dataset(json_data)
        # dataset = self._reduce_dataset(dataset)

        text_clf = Pipeline([
            ('vect', FeatureUnion(
                transformer_list=[
                    ('tfidf', TfidfVectorizer(ngram_range=(1, 2),
                                              tokenizer=my_tokenizer)),
                    ('insults', InsultFeatures(insult_words_regex=self.insult_words_regex,
                                               address_words_regex=self.address_words_regex,
                                               weak_insult_words_regex=self.weak_insult_words_regex))
                ],
                transformer_weights={
                    'tfidf': 1.0,
                    'insults': 1.0
                })),
            # ('todense', DenseTransformer()),
            ('scaler', StandardScaler(with_mean=False)),
            ('clf', SVC(verbose=True, class_weight='auto', kernel='linear', max_iter=10000))
        ])

        parameters = {'clf__C': (1, 10, 100),
                      'clf__kernel': ('linear', 'poly'),
                      'clf__gamma': (1e-11, 1e-7, 1e-5),
                      'vect__tfidf__ngram_range': [(1, 2)],
                      'clf__class_weight': ['auto'],
                      # 'clf__loss': ('hinge', 'squared_hinge', 'squared_loss'),
                      # 'clf__penalty': ('l2', 'elasticnet', 'l1'),
                      # 'vect__tfidf__max_df': (0.75, 0.9, 1.0),
                      # 'vect__tfidf__use_idf': (True, False),
                      # 'vect__addreses__var': (0, 1)
                      }
        gs_clf = GridSearchCV(text_clf, parameters, n_jobs=-1, scoring='f1', verbose=5)
        gs_clf = gs_clf.fit(dataset['data'], dataset['target'])
        best_parameters, score, _ = max(gs_clf.grid_scores_, key=lambda x: x[1])
        for param_name in sorted(parameters.keys()):
            print("%s: %r" % (param_name, best_parameters[param_name]))
        print(score)

    def _cross_validate(self, json_data):
        dataset = self._json_to_dataset(json_data)
        # dataset = self._reduce_dataset(dataset)

        text_clf = Pipeline([
            ('vect', FeatureUnion(
                [
                ('tfidf', TfidfVectorizer(ngram_range=(1, 2),
                                          tokenizer=my_tokenizer)),
                ('inaults', InsultFeatures())
                ]
            )),
            ('clf',   SGDClassifier(class_weight='auto',
                                    n_jobs=-1,
                                    penalty='elasticnet',
                                    alpha=9e-7,
                                    loss='hinge',
                                    n_iter=10))
        ])
        score = cross_validation.cross_val_score(text_clf,
                                                 dataset['data'],
                                                 dataset['target'],
                                                 cv=5,
                                                 scoring='f1',
                                                 n_jobs=-1,
                                                 verbose=5)
        print(score)

    def test_tokenizer(self, json_data):
        dataset = self._json_to_dataset(json_data)

        for text in dataset['data'][:20]:
            try:
                print(text)
                print(my_tokenizer(text))
            except:
                pass
        exit()

    def plot_some_graphs(self, json_data):
        dataset = self._json_to_dataset(json_data)
        # dataset = self._reduce_dataset(dataset)
        at = InsultFeatures(self.insult_words_regex, self.address_words_regex, self.weak_insult_words_regex)

        ins = []
        not_ins = []
        for i in range(len(dataset['target'])):
            if dataset['target'][i]:
                ins.append(dataset['data'][i])
            else:
                not_ins.append(dataset['data'][i])

        print(len(not_ins), len(ins))
        ins_array = at.transform(ins).toarray()
        not_ins_array = at.transform(not_ins).toarray()

        rand_arr_ins = [random.random() * 10. for i in range(len(ins_array))]
        rand_arr_not_ins = [random.random() * 10. for i in range(len(not_ins_array))]

        # plt.plot(ins_array[:, 0], rand_arr_ins, 'r.')
        # plt.plot(not_ins_array[:, 0], rand_arr_not_ins, 'b.')

        plt.plot(ins_array[:, 0], ins_array[:, 1], 'r.')
        plt.plot(not_ins_array[:, 0], not_ins_array[:, 1], 'b.')

        plt.show()

    def test(self):
        json_file = open('discussions.json', encoding='utf-8', errors='replace')
        # json_file = open('test_discussions/learn.json', encoding='utf-8', errors='replace')

        json_data = json.load(json_file)

        # self._cross_validate(json_data)
        self._grid_search(json_data)
        # self.test_tokenizer(json_data)
        # self.train(json_data)
        # self.plot_some_graphs(json_data)

        # dataset = self._json_to_dataset(json_data)
        # at = AddressTransformet()
        # ins = []
        # for i in range(len(dataset['data'])):
        #     if (dataset['target'][i]):
        #         ins.append(dataset['data'][i])
        # d = dict()
        # for i in dataset['data']:
        #     for tok in my_tokenizer(i):
        #         for w in bad_words_part:
        #             if w in tok:
        #                 d.setdefault(tok, 0)
        #                 d[tok] += 1
        #         for w in bad_words_begin:
        #             if tok.startswith(w):
        #                 d.setdefault(tok, 0)
        #                 d[tok] += 1
        #
        # import operator
        # for i in sorted(d.items(), key=operator.itemgetter(1)):
        #     if (i[1] > 10):
        #         print(i)

        # print(at.transform(ins))
    def _test_split(self):
        start_time = time.time()
        json_file = open('discussions.json', encoding='utf-8', errors='replace')
        # json_file = open('test_discussions/learn.json', encoding='utf-8', errors='replace')
        json_data = json.load(json_file)

        dataset = self._json_to_dataset(json_data)
        dataset['data'], data_test, dataset['target'], target_test \
            = cross_validation.train_test_split(dataset['data'], dataset['target'], test_size=0.2, random_state=1)

        self.train(dataset)
        print('Training done')
        print(f1_score(target_test, self.text_clf.predict(data_test), pos_label=True))
        print("--- %.1f ---" % ((time.time() - start_time) / 60))

    def _test_if_i_broke_something(self):
        json_file = open('test_discussions/learn.json')
        json_data = json.load(json_file)
        self.train(json_data)
        json_test = open('test_discussions/test.json')
        json_test_data = json.load(json_test)
        print(self.classify(json_test_data))

if __name__ == '__main__':
    d = InsultDetector()
    # d.test()
    d._test_split()
#     d._test_if_i_broke_something()