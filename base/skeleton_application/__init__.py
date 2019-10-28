from base.common.skeleton_base import SkeletonBase
from .router import *
from .webhook import *


class SkeletonApplication(SkeletonBase):

    def quote_simulate(self, service_id, quote_id):
        """
        Invoked when application receives a quote_simulate call

        Receives:
            service_id - unique service id. Must be set in configuration file
            quote_id - UUID of quote

        Returns:
            {
                "quote_properties": [
                    {
                        "data" : ":data",
                        "id" : ":uuid",
                        "namespace": ":namespace"
                    },
                    ...

                ],
                "coverage_properties": [
                    {
                        "data" : ":data",
                        "coverage_id": ":uuid",
                        "id" : ":uuid",
                        "namespace": ":namespace"
                    },
                    ...
                ]
            }
        """
        raise NotImplementedError('No polling handler implemented')


SkeletonBase.register(SkeletonApplication)
