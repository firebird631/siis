from ._http_manager import _HTTPManager


class HTTP(_HTTPManager):
    def create_internal_transfer(self, **kwargs):
        """
        Transfers funds between the different sections of an individuals
        account (not between subaccounts). For example, between the spot and
        derivatives accounts.

        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-createinternaltransfer.
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/private/transfer"
        if self._verify_string(kwargs, "amount"):
            return self._submit_request(
                method="POST",
                path=self.endpoint + suffix,
                query=kwargs,
                auth=True
            )
        else:
            self.logger.error("amount must be in string format")

    def create_subaccount_transfer(self, **kwargs):
        """
        Transfers funds between the parent and child (sub) accounts.

        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-createsubaccounttransfer.
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/private/sub-member/transfer"

        if self._verify_string(kwargs, "amount"):
            return self._submit_request(
                method="POST",
                path=self.endpoint + suffix,
                query=kwargs,
                auth=True
            )
        else:
            self.logger.error("amount must be in string format")

    def query_transfer_list(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-querytransferlist.
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/private/transfer/list"

        return self._submit_request(
            method="GET",
            path=self.endpoint + suffix,
            query=kwargs,
            auth=True
        )

    def query_subaccount_list(self):
        """
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/private/sub-member/member-ids"

        return self._submit_request(
            method="GET",
            path=self.endpoint + suffix,
            query={},
            auth=True
        )

    def query_subaccount_transfer_list(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-querysubaccounttransferlist.
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/private/sub-member/transfer/list"

        return self._submit_request(
            method="GET",
            path=self.endpoint + suffix,
            query=kwargs,
            auth=True
        )

    def query_supported_deposit_list(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-allowdepositlist.
        :returns: Request results as dictionary.
        """

        suffix = "/asset/v1/public/deposit/allowed-deposit-list"

        return self._submit_request(
            method="GET",
            path=self.endpoint + suffix,
            query=kwargs,
            auth=True
        )

    def query_deposit_records(self, **kwargs):
        """
        Rules: Only query the deposit records of spot accounts order by id in
        reverse order. The maximum difference between the start time and the
        end time is 30 days.

        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-depositsrecordquery.
        :returns: Request results as dictionary.
        """

        return self._submit_request(
            method="GET",
            path=self.endpoint + "/asset/v1/private/deposit/record/query",
            query=kwargs,
            auth=True
        )

    def query_withdraw_records(self, **kwargs):
        """
        Rule: order by id in reverse order. The maximum difference between
        the start time and the end time is 30 days.

        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-withdrawrecordquery.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="GET",
            path=self.endpoint + "/asset/v1/private/withdraw/record/query",
            query=kwargs,
            auth=True
        )

    def query_coin_info(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-coin_info_query.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="GET",
            path=self.endpoint + "/asset/v1/private/coin-info/query",
            query=kwargs,
            auth=True
        )

    def query_asset_info(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-asset_info_query.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="GET",
            path=self.endpoint + "/asset/v1/private/asset-info/query",
            query=kwargs,
            auth=True
        )

    def withdraw(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-withdraw_info.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/withdraw",
            query=kwargs,
            auth=True
        )

    def cancel_withdrawal(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-cancel_withdraw.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/withdraw/cancel",
            query=kwargs,
            auth=True
        )

    def query_deposit_address(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-deposit_addr_info.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/transferable-subs/save",
            query=kwargs,
            auth=True
        )

    def enable_universal_transfer(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-deposit_addr_info.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/transferable-subs/save",
            query=kwargs,
            auth=True
        )

    def create_universal_transfer(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-deposit_addr_info.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/universal/transfer",
            query=kwargs,
            auth=True
        )

    def query_universal_transfer_list(self, **kwargs):
        """
        Rules: Subaccount can not deposit

        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-deposit_addr_info.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/transferable-subs/save",
            query=kwargs,
            auth=True
        )

    def enable_universal_transfer(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-enableuniversaltransfer.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/transferable-subs/save",
            query=kwargs,
            auth=True
        )

    def create_universal_transfer(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-createuniversaltransfer.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="POST",
            path=self.endpoint + "/asset/v1/private/universal/transfer",
            query=kwargs,
            auth=True
        )

    def query_universal_transfer_list(self, **kwargs):
        """
        :param kwargs: See
            https://bybit-exchange.github.io/docs/account_asset/#t-queryuniversetransferlist.
        :returns: Request results as dictionary.

        """
        return self._submit_request(
            method="GET",
            path=self.endpoint + "/asset/v1/private/universal/transfer/list",
            query=kwargs,
            auth=True
        )
