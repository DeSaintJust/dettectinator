"""
Dettectinator - The Python library to your DeTT&CT YAML files.
Authors:
    Martijn Veken, Sirius Security
    Ruben Bouman, Sirius Security
License: GPL-3.0 License

Parts this module have been taken from the Microsoft MSAL library for Python:
https://github.com/AzureAD/microsoft-authentication-library-for-python/

On those parts the following terms and conditions are applicable:

The MIT License (MIT)

Copyright (c) Microsoft Corporation.
All rights reserved.

This code is licensed under the MIT License.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files(the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions :

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


from msal import PublicClientApplication
from msal.application import _clean_up, _merge_claims_challenge_and_capabilities
import msal


class PublicClientApplicationPatch(PublicClientApplication):
    """
    This class patches the msal.PublicClientApplication class so that it accepts additional headers for the
    device flow initiation request. This allows specifying the OS/Platform type by setting an appropriate
    user agent value.
    """

    def __init__(self, client_id, client_credential=None, **kwargs):
        super().__init__(client_id, client_credential, **kwargs)

    def initiate_device_flow(self, scopes=None, **kwargs):
        """Initiate a Device Flow instance,
        which will be used in :func:`~acquire_token_by_device_flow`.

        :param list[str] scopes:
            Scopes requested to access a protected API (a resource).
        :return: A dict representing a newly created Device Flow object.

            - A successful response would contain "user_code" key, among others
            - an error response would contain some other readable key/value pairs.
        """
        correlation_id = msal.telemetry._get_new_correlation_id()

        # PATCH
        # Add the supplied headers to the client request id header
        headers = kwargs.pop("headers", {})
        headers.update({msal.telemetry.CLIENT_REQUEST_ID: correlation_id})
        # /PATCH

        flow = self.client.initiate_device_flow(
            scope=self._decorate_scope(scopes or []),
            headers=headers,
            **kwargs)
        flow[self.DEVICE_FLOW_CORRELATION_ID] = correlation_id
        return flow

    def acquire_token_by_device_flow(self, flow, claims_challenge=None, **kwargs):
        """Obtain token by a device flow object, with customizable polling effect.

        :param dict flow:
            A dict previously generated by :func:`~initiate_device_flow`.
            By default, this method's polling effect  will block current thread.
            You can abort the polling loop at any time,
            by changing the value of the flow's "expires_at" key to 0.
        :param claims_challenge:
            The claims_challenge parameter requests specific claims requested by the resource provider
            in the form of a claims_challenge directive in the www-authenticate header to be
            returned from the UserInfo Endpoint and/or in the ID Token and/or Access Token.
            It is a string of a JSON object which contains lists of claims being requested from these locations.

        :return: A dict representing the json response from AAD:

            - A successful response would contain "access_token" key,
            - an error response would contain "error" and usually "error_description".
        """
        telemetry_context = self._build_telemetry_context(
            self.ACQUIRE_TOKEN_BY_DEVICE_FLOW_ID,
            correlation_id=flow.get(self.DEVICE_FLOW_CORRELATION_ID))

        # PATCH
        # Add the supplied headers to the client request id header
        headers = kwargs.pop("headers", {})
        headers.update(telemetry_context.generate_headers())
        # /PATCH

        response = _clean_up(self.client.obtain_token_by_device_flow(
            flow,
            data=dict(
                kwargs.pop("data", {}),
                code=flow["device_code"],  # 2018-10-4 Hack:
                    # during transition period,
                    # service seemingly need both device_code and code parameter.
                claims=_merge_claims_challenge_and_capabilities(
                    self._client_capabilities, claims_challenge),
                ),
            headers=headers,
            **kwargs))
        telemetry_context.update_telemetry(response)
        return response