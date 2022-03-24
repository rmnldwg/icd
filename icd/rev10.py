import os
from typing import Optional
from dataclasses import dataclass, field

import untangle
import requests

from .base import ICDEntry, ICDRoot, ICDChapter, ICDBlock, ICDCategory


@dataclass
class ICD10Entry(ICDEntry):
    """
    Class representing an entry in the 10th ICD revision.
    """
    revision: str = "10"
    
    def request(
        self, 
        auth_method: str = "args", 
        icd_api_id: Optional[str] = None, 
        icd_api_secret: Optional[str] = None,
        api_ver: int = 2,
        lang: str = "en",
    ) -> str:
        """
        Return information on an entry from WHO's ICD API.
        
        This function provides two ways for authenticating to the API: One can 
        simply provide the `ClientId` as `icd_api_id` and the `ClientSecret` as 
        `icd_api_secret`, in which case `auth_method` must be set to `"args"`. 
        Or the two strings can be set as environment variables aptly named 
        `ICD_API_ID` and `ICD_API_SECRET`. In that case, set `auth_method` to 
        `"env"`.
        
        There are two major versions of the ICD API that can be chosen by 
        setting `api_ver` to either `1` ot `2`.
        
        The API provides its response in different languages, which can be 
        selected by setting `lang`, e.g. to `"en"`.
        """
        if auth_method == "env":
            icd_api_id = os.getenv("ICD_API_ID")
            icd_api_secret = os.getenv("ICD_API_SECRET")
        elif auth_method != "args":
            raise ValueError("`auth_method` must be either 'args' or 'env'.")
        
        if icd_api_id is None or icd_api_secret is None:
            raise ValueError("Both ICD_API_ID and ICD_API_SECRET must be set.")
        
        # Authenticate
        token_endpoint = "https://icdaccessmanagement.who.int/connect/token"
        payload = {
            "client_id": icd_api_id,
            "client_secret": icd_api_secret,
            "scope": "icdapi_access",
            "grantkind": "client_credentials"
        }
        response = requests.post(token_endpoint, data=payload).json()
        access_token = response["access_token"]
        
        # Make request
        year = self.get_root().year
        uri = f"https://id.who.int/icd/release/10/{year}/{self.code}"
        headers = {
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
            "Accept-Language": lang,
            "API-Version": f"v{api_ver}",
        }
        response = requests.get(uri, headers=headers)
        
        # check if request was successful, if not, try to get another release
        if response.status_code != requests.codes.ok:
            fallback_uri = f"https://id.who.int/icd/release/10/{self.code}"
            response = requests.get(fallback_uri, headers=headers)
            
            if response.status_code == requests.codes.ok:
                latest_uri = response.json()["latestRelease"]
                response = requests.get(latest_uri, headers=headers)
            else:
                raise requests.HTTPError(
                    f"Could not resolve code {self.code}", 
                    response=response
                )
        
        return response



@dataclass
class ICD10Root(ICDRoot, ICD10Entry):
    """"""

@dataclass
class ICD10Chapter(ICDChapter, ICD10Entry):
    """"""

@dataclass
class ICD10Block(ICDBlock, ICD10Entry):
    """"""

@dataclass
class ICD10Category(ICDCategory, ICD10Entry):
    """"""