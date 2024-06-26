import time
import numpy as np
from scipy.optimize import minimize

from bayeso.bo import base_bo
from bayeso import constants
from bayeso.gp import gp
from bayeso.gp import gp_kernel
from bayeso.utils import utils_bo
from bayeso.utils import utils_logger


class MOBO(base_bo.BaseBO):
    def __init__(self, range_X: np.ndarray,
        str_cov: str=constants.STR_COV,
        str_acq: str=constants.STR_BO_ACQ,
        normalize_Y: bool=constants.NORMALIZE_RESPONSE,
        use_ard: bool=constants.USE_ARD,
        prior_mu: constants.TYPING_UNION_CALLABLE_NONE=None,
        str_optimizer_method_gp: str=constants.STR_OPTIMIZER_METHOD_GP,
        str_optimizer_method_bo: str=constants.STR_OPTIMIZER_METHOD_AO,
        str_modelselection_method: str=constants.STR_MODELSELECTION_METHOD,
        str_exp: str=None,
        debug: bool=False
    ):
        assert isinstance(range_X, np.ndarray)
        assert isinstance(str_cov, str)
        assert isinstance(str_acq, str)
        assert isinstance(normalize_Y, bool)
        assert isinstance(use_ard, bool)
        assert isinstance(str_optimizer_method_bo, str)
        assert isinstance(str_optimizer_method_gp, str)
        assert isinstance(str_modelselection_method, str)
        assert isinstance(str_exp, (type(None), str))
        assert isinstance(debug, bool)
        assert callable(prior_mu) or prior_mu is None
        assert len(range_X.shape) == 2
        assert range_X.shape[1] == 2
        assert (range_X[:, 0] <= range_X[:, 1]).all()
        assert str_cov in constants.ALLOWED_COV
        assert str_acq in constants.ALLOWED_BO_ACQ
        assert str_optimizer_method_gp in constants.ALLOWED_OPTIMIZER_METHOD_GP
        assert str_optimizer_method_bo in constants.ALLOWED_OPTIMIZER_METHOD_BO
        assert str_modelselection_method in constants.ALLOWED_MODELSELECTION_METHOD

        str_surrogate = 'gp'
        assert str_surrogate in constants.ALLOWED_SURROGATE

        super().__init__(range_X, str_surrogate, str_acq,
            str_optimizer_method_bo, normalize_Y, str_exp, debug)

        self.str_cov = str_cov
        self.use_ard = use_ard
        self.str_optimizer_method_gp = str_optimizer_method_gp
        self.str_modelselection_method = str_modelselection_method
        self.prior_mu = prior_mu

    def _optimize(self, fun_negative_acquisition: constants.TYPING_CALLABLE,
        str_sampling_method: str,
        num_samples: int,
        seed: int=None,
    ) -> constants.TYPING_TUPLE_TWO_ARRAYS:
        list_next_point = []

        list_bounds = self._get_bounds()
        initials = self.get_samples(str_sampling_method,
            num_samples=num_samples, seed=seed)

        for arr_initial in initials:
            next_point = minimize(
                fun_negative_acquisition,
                x0=arr_initial,
                bounds=list_bounds,
                method=self.str_optimizer_method_bo,
                options={'disp': False}
            )
            next_point_x = next_point.x
            list_next_point.append(next_point_x)
            if self.debug:
                self.logger.debug('acquired sample: %s',
                    utils_logger.get_str_array(next_point_x))

        next_points = np.array(list_next_point)
        next_point = utils_bo.get_best_acquisition_by_evaluation(
            next_points, fun_negative_acquisition)[0]
        return next_point, next_points

    def compute_posteriors(self,
        X_train: np.ndarray, Y_train: np.ndarray,
        X_test: np.ndarray, cov_X_X: np.ndarray,
        inv_cov_X_X: np.ndarray, hyps: dict
    ) -> np.ndarray:
        assert isinstance(X_train, np.ndarray)
        assert isinstance(Y_train, np.ndarray)
        assert isinstance(X_test, np.ndarray)
        assert isinstance(cov_X_X, np.ndarray)
        assert isinstance(inv_cov_X_X, np.ndarray)
        assert isinstance(hyps, dict)
        assert len(X_train.shape) == 2 or len(X_train.shape) == 3
        assert len(Y_train.shape) == 2
        assert len(X_test.shape) == 2 or len(X_test.shape) == 3
        assert len(cov_X_X.shape) == 2
        assert len(inv_cov_X_X.shape) == 2
        assert Y_train.shape[1] == 1
        assert X_train.shape[0] == Y_train.shape[0]
        if len(X_train.shape) == 2:
            assert X_test.shape[1] == X_train.shape[1] == self.num_dim
        else:
            assert X_test.shape[2] == X_train.shape[2] == self.num_dim
        assert cov_X_X.shape[0] == cov_X_X.shape[1] == X_train.shape[0]
        assert inv_cov_X_X.shape[0] == inv_cov_X_X.shape[1] == X_train.shape[0]

        pred_mean, pred_std, _ = gp.predict_with_cov(
            X_train, Y_train, X_test,
            cov_X_X, inv_cov_X_X, hyps, str_cov=self.str_cov,
            prior_mu=self.prior_mu, debug=self.debug
        )

        pred_mean = np.squeeze(pred_mean, axis=1)
        pred_std = np.squeeze(pred_std, axis=1)

        return pred_mean, pred_std

    def compute_acquisitions(self, X: np.ndarray,
        X_train: np.ndarray, Y_train: np.ndarray,
        cov_X_X: np.ndarray, inv_cov_X_X: np.ndarray, hyps: dict
    ) -> np.ndarray:
        assert isinstance(X, np.ndarray)
        assert isinstance(X_train, np.ndarray)
        assert isinstance(Y_train, np.ndarray)
        assert isinstance(cov_X_X, np.ndarray)
        assert isinstance(inv_cov_X_X, np.ndarray)
        assert isinstance(hyps, dict)
        assert len(X.shape) == 1 or len(X.shape) == 2 or len(X.shape) == 3
        assert len(X_train.shape) == 2 or len(X_train.shape) == 3
        assert len(Y_train.shape) == 2
        assert len(cov_X_X.shape) == 2
        assert len(inv_cov_X_X.shape) == 2
        assert Y_train.shape[1] == 1
        assert X_train.shape[0] == Y_train.shape[0]

        if len(X.shape) == 1:
            X = np.atleast_2d(X)

        if len(X_train.shape) == 2:
            assert X.shape[1] == X_train.shape[1] == self.num_dim
        else:
            assert X.shape[2] == X_train.shape[2] == self.num_dim

        assert cov_X_X.shape[0] == cov_X_X.shape[1] == X_train.shape[0]
        assert inv_cov_X_X.shape[0] == inv_cov_X_X.shape[1] == X_train.shape[0]

        fun_acquisition = utils_bo.choose_fun_acquisition(self.str_acq, hyps.get('noise', None))

        pred_mean, pred_std = self.compute_posteriors(
            X_train, Y_train, X,
            cov_X_X, inv_cov_X_X, hyps
        )

        acquisitions = fun_acquisition(
            pred_mean=pred_mean, pred_std=pred_std, Y_train=Y_train
        )
        acquisitions *= constants.MULTIPLIER_ACQ

        return acquisitions

    def optimize(self, X_train: np.ndarray, Y_train: np.ndarray,
        str_sampling_method: str=constants.STR_SAMPLING_METHOD_AO,
        num_samples: int=constants.NUM_SAMPLES_AO,
        seed: int=None,
    ) -> constants.TYPING_TUPLE_ARRAY_DICT:
        assert isinstance(X_train, np.ndarray)
        assert isinstance(Y_train, np.ndarray)
        assert isinstance(str_sampling_method, str)
        assert isinstance(num_samples, int)
        assert isinstance(seed, (type(None), int))
        assert len(X_train.shape) == 2
        assert len(Y_train.shape) == 2
        assert Y_train.shape[1] == 2
        assert X_train.shape[0] == Y_train.shape[0]
        assert X_train.shape[1] == self.num_dim
        assert num_samples > 0
        assert str_sampling_method in constants.ALLOWED_SAMPLING_METHOD

        time_start = time.time()

        Y_train_1 = Y_train[:, [0]]
        Y_train_2 = Y_train[:, [1]]

        Y_train_orig_1 = Y_train_1
        Y_train_orig_2 = Y_train_2

        if self.normalize_Y:
            if self.debug:
                self.logger.debug('Responses are normalized.')

            Y_train_1 = utils_bo.normalize_min_max(Y_train_1)
            Y_train_2 = utils_bo.normalize_min_max(Y_train_2)

        time_start_surrogate = time.time()

        cov_X_X_1, inv_cov_X_X_1, hyps_1 = gp_kernel.get_optimized_kernel(
            X_train, Y_train_1,
            self.prior_mu, self.str_cov,
            str_optimizer_method=self.str_optimizer_method_gp,
            str_modelselection_method=self.str_modelselection_method,
            use_ard=self.use_ard,
            debug=self.debug
        )

        cov_X_X_2, inv_cov_X_X_2, hyps_2 = gp_kernel.get_optimized_kernel(
            X_train, Y_train_2,
            self.prior_mu, self.str_cov,
            str_optimizer_method=self.str_optimizer_method_gp,
            str_modelselection_method=self.str_modelselection_method,
            use_ard=self.use_ard,
            debug=self.debug
        )

        time_end_surrogate = time.time()

        time_start_acq = time.time()
        fun_negative_acquisition_1 = lambda X_test: -1.0 * self.compute_acquisitions(
            X_test, X_train, Y_train_1, cov_X_X_1, inv_cov_X_X_1, hyps_1
        )
        fun_negative_acquisition_2 = lambda X_test: -1.0 * self.compute_acquisitions(
            X_test, X_train, Y_train_2, cov_X_X_2, inv_cov_X_X_2, hyps_2
        )
        log_weight = np.random.RandomState(seed + 101).uniform(low=-3, high=3)

        fun_negative_acquisition = lambda X_test: fun_negative_acquisition_1(X_test) + 10**log_weight * fun_negative_acquisition_2(X_test)

        next_point, next_points = self._optimize(fun_negative_acquisition,
            str_sampling_method=str_sampling_method,
            num_samples=num_samples,
            seed=seed)

        next_point = utils_bo.check_points_in_bounds(
            next_point[np.newaxis, ...], np.array(self._get_bounds()))[0]
        next_points = utils_bo.check_points_in_bounds(
            next_points, np.array(self._get_bounds()))

        time_end_acq = time.time()

        acquisitions = fun_negative_acquisition(next_points)
        time_end = time.time()

        dict_info = {
            'next_points': next_points,
            'acquisitions': acquisitions,
            'Y_original_1': Y_train_orig_1,
            'Y_original_2': Y_train_orig_2,
            'Y_normalized_1': Y_train_1,
            'Y_normalized_2': Y_train_2,
            'cov_X_X_1': cov_X_X_1,
            'inv_cov_X_X_1': inv_cov_X_X_1,
            'hyps_1': hyps_1,
            'cov_X_X_2': cov_X_X_2,
            'inv_cov_X_X_2': inv_cov_X_X_2,
            'hyps_2': hyps_2,
            'time_surrogate': time_end_surrogate - time_start_surrogate,
            'time_acq': time_end_acq - time_start_acq,
            'time_overall': time_end - time_start,
        }

        if self.debug:
            self.logger.debug('overall time consumed to acquire: %.4f sec.', time_end - time_start)

        return next_point, dict_info
