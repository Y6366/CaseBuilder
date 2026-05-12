# -*- coding: utf-8 -*-
"""
{case_description}
"""
import pytest
{imports}


module = "{module_name}"


class {class_name}({base_class}):
    """
    {class_docstring}
    """

    def setup(self, case_name=None):
        case_name = "{class_name}"
        if not super({class_name}, self).setup(case_name):
            return False

        {setup_body}

        self.init_success_flg = True
        self.ms_log.info("The case setup success")
        return self.init_success_flg

    @pytest.mark.level1
    @pytest.mark.timeout({timeout})
    {env_markers}
    def test_run(self):
        """
        test_run
        """
        assert self.init_success_flg
        self.ms_log.info("The case test is running")
        self.perf_acc_flag = True

        {test_run_body}

        # 一致性校验
        {consistency_check}

        if not self.perf_acc_flag:
            self.ms_log.error("Something wrong with infer, pls check error log.")
            assert False

        self.ms_log.info("The case test is success")

    def teardown(self):
        self.ms_log.info("The case teardown is running")
        super({class_name}, self).teardown()
        return True
