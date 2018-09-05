from traffic_data_ph import DataPh
from traffic_data_input import DataInput
from TensorflowToolbox.utility import file_io
import tensorflow as tf

from TensorflowToolbox.model_flow import model_trainer as mt
from TensorflowToolbox.model_flow import save_func as sf
from TensorflowToolbox.utility import utility_func as uf
from TensorflowToolbox.utility import result_obj as ro
import cv2
import numpy as np
import os

TF_VERSION = tf.__version__.split(".")[1]


class NetFlow(object):
    def __init__(self, model_params, load_train, load_test):

        self.load_train = load_train
        self.load_test = load_test
        self.model_params = model_params
        self.check_model_params(model_params)

        self.desmap_scale = self.model_params["desmap_scale"]

        if load_train:
            self.train_data_input = DataInput(model_params, is_train=True)
        if load_test:
            self.test_data_input = DataInput(model_params, is_train=False)

        self.data_ph = DataPh(model_params)
        model = file_io.import_module_class(model_params["model_def_name"],
                                            "Model")
        self.model = model(self.data_ph, model_params)
        # self.loss = self.model.get_loss()
        self.count_diff = self.model.get_count_diff()
        self.loss = self.model.get_loss()
        self.train_op = self.model.get_train_op()

    @staticmethod
    def check_model_params(model_params):
        field_list = ["restore_model", "model_dir", "max_training_iter",
                      "train_log_dir", "test_per_iter", "save_per_iter"]

        for field in field_list:
            assert(field in model_params)

    def get_feed_dict(self, sess, is_train):
        feed_dict = dict()
        if is_train:
            input_v, label_v, mask_v, file_line_v = sess.run([
                self.train_data_input.get_input(),
                self.train_data_input.get_label(),
                self.train_data_input.get_mask(),
                self.train_data_input.get_file_line()])
        else:
            input_v, label_v, mask_v, file_line_v = sess.run([
                self.test_data_input.get_input(),
                self.test_data_input.get_label(),
                self.test_data_input.get_mask(),
                self.test_data_input.get_file_line()])

        feed_dict[self.data_ph.get_input()] = input_v
        feed_dict[self.data_ph.get_label()] = label_v * self.desmap_scale
        feed_dict[self.data_ph.get_mask()] = mask_v

        self.file_line = file_line_v

        return feed_dict

    def get_feed_dict_da(self, sess, is_train):
        feed_dict = dict()
        if is_train:
            input_v, label_v, mask_v, file_line_v = sess.run([
                self.train_data_input.get_input(),
                self.train_data_input.get_label(),
                self.train_data_input.get_mask(),
                self.train_data_input.get_file_line()])
        else:
            input_v, label_v, mask_v, file_line_v = sess.run([
                self.test_data_input.get_input(),
                self.test_data_input.get_label(),
                self.test_data_input.get_mask(),
                self.test_data_input.get_file_line()])

        feed_dict[self.data_ph.get_input()] = input_v
        feed_dict[self.data_ph.get_label()] = label_v * self.desmap_scale
        feed_dict[self.data_ph.get_mask()] = mask_v

        return feed_dict

    def init_var(self, sess):
        sf.add_train_var()
        sf.add_loss()
        sf.add_image("image_to_write", 4)
        self.saver = tf.train.Saver()

        if TF_VERSION > '11':
            if self.load_train:
                self.sum_writer = tf.summary.FileWriter(self.model_params["train_log_dir"],
                                                        sess.graph)
            self.summ = tf.summary.merge_all()
            init_op = tf.global_variables_initializer()
        else:
            if self.load_train:
                self.sum_writer = tf.train.SummaryWriter(self.model_params["train_log_dir"],
                                                         sess.graph)
            self.summ = tf.merge_all_summaries()
            init_op = tf.initialize_all_variables()

        sess.run(init_op)

        if self.model_params["restore_model"]:
            sf.restore_model(sess, self.saver, self.model_params["model_dir"],
                             self.model_params["restore_model_name"])

    def mainloop(self):
        config_proto = uf.define_graph_config(self.model_params["gpu_fraction"])
        sess = tf.Session(config=config_proto)
        self.init_var(sess)
        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(coord=coord, sess=sess)

        if self.load_train:
            for i in range(self.model_params["max_training_iter"]):
                feed_dict = self.get_feed_dict(sess, is_train=True)
                # self.check_feed_dict(feed_dict)
                _, tloss_v, tcount_diff_v = sess.run([self.train_op,
                                                      self.loss, self.count_diff], feed_dict)

                if i % self.model_params["test_per_iter"] == 0:
                    feed_dict = self.get_feed_dict(sess, is_train=False)
                    loss_v, summ_v, count_diff_v = \
                        sess.run([self.loss,
                                  self.summ, self.count_diff], feed_dict)

                    tcount_diff_v /= self.desmap_scale
                    count_diff_v /= self.desmap_scale

                    print_string = "i: %d, train_loss: %.2f, test_loss: %.2f, " \
                        "train_count_diff: %.2f, test_count_diff: %.2f" %\
                        (i, tloss_v, loss_v, tcount_diff_v, count_diff_v)

                    print(print_string)
                    file_io.save_string(print_string,
                                        self.model_params["train_log_dir"] +
                                        self.model_params["string_log_name"])

                    self.sum_writer.add_summary(summ_v, i)
                    sf.add_value_sum(self.sum_writer, tloss_v, "train_loss", i)
                    sf.add_value_sum(self.sum_writer, loss_v, "test_loss", i)
                    sf.add_value_sum(self.sum_writer, tcount_diff_v,
                                     "train_count_diff", i)
                    sf.add_value_sum(self.sum_writer, count_diff_v,
                                     "test_count_diff", i)
                    #sf.add_value_sum(self.sum_writer, stage2_v, "stage2", i)
                    #sf.add_value_sum(self.sum_writer, stage3_v, "stage3", i)

                if i != 0 and (i % self.model_params["save_per_iter"] == 0 or
                               i == self.model_params["max_training_iter"] - 1):
                    sf.save_model(sess, self.saver, self.model_params["model_dir"], i)

        elif self.load_test:
            file_len = file_io.get_file_length(self.model_params["test_file_name"])
            batch_size = self.model_params["batch_size"]
            test_iter = int(file_len / batch_size) + 1
            result_file_name = self.model_params["result_file_name"]
            result_obj = ro.ResultObj(result_file_name)

            for i in range(test_iter):
                feed_dict = self.get_feed_dict(sess, is_train=False)
                loss_v, count_v, label_count_v = sess.run([self.loss, self.count,
                                                           self.label_count], feed_dict)
                count_v /= self.desmap_scale
                label_count_v /= self.desmap_scale

                file_line = [f.decode("utf-8").split(" ")[0] for f in self.file_line]
                count_v = result_obj.float_to_str(count_v, "%.2f")
                label_count_v = result_obj.float_to_str(label_count_v, "%.2f")

                result_obj.add_to_list(file_line, label_count_v, count_v)
                print(file_line[0], count_v[0], label_count_v[0])

            result_obj.save_to_file(True)

        coord.request_stop()
        coord.join(threads)
