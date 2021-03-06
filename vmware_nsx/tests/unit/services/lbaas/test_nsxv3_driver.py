# Copyright (c) 2017 VMware, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from neutron.tests import base
from neutron_lbaas.services.loadbalancer import data_models as lb_models
from neutron_lib import context
from neutron_lib import exceptions as n_exc

from vmware_nsx.db import db as nsx_db
from vmware_nsx.services.lbaas import base_mgr
from vmware_nsx.services.lbaas.nsx_v3.implementation import lb_utils
from vmware_nsx.services.lbaas.nsx_v3.v2 import lb_driver_v2


LB_VIP = '10.0.0.10'
LB_ROUTER_ID = 'router-x'
LB_ID = 'xxx-xxx'
LB_TENANT_ID = 'yyy-yyy'
LB_SERVICE_ID = 'service-1'
LB_BINDING = {'loadbalancer_id': LB_ID,
              'lb_service_id': LB_SERVICE_ID,
              'lb_router_id': LB_ROUTER_ID,
              'vip_address': LB_VIP}
LB_NETWORK = {'router:external': False,
              'id': 'xxxxx',
              'name': 'network-1'}
LISTENER_ID = 'listener-x'
APP_PROFILE_ID = 'appp-x'
LB_VS_ID = 'vs-x'
LB_APP_PROFILE = {
    "resource_type": "LbHttpProfile",
    "description": "my http profile",
    "id": APP_PROFILE_ID,
    "display_name": "httpprofile1",
    "ntlm": False,
    "request_header_size": 1024,
    "http_redirect_to_https": False,
    "idle_timeout": 1800,
    "x_forwarded_for": "INSERT",
}
LISTENER_BINDING = {'loadbalancer_id': LB_ID,
                    'listener_id': LISTENER_ID,
                    'app_profile_id': APP_PROFILE_ID,
                    'lb_vs_id': LB_VS_ID}
POOL_ID = 'ppp-qqq'
LB_POOL_ID = 'pool-xx'
LB_POOL = {
    "display_name": "httppool1",
    "description": "my http pool",
    "id": LB_POOL_ID,
    "algorithm": "ROUND_ROBIN",
}
POOL_BINDING = {'loadbalancer_id': LB_ID,
                'pool_id': POOL_ID,
                'lb_pool_id': LB_POOL_ID,
                'lb_vs_id': LB_VS_ID}
MEMBER_ID = 'mmm-mmm'
MEMBER_ADDRESS = '10.0.0.200'
LB_MEMBER = {'display_name': 'member1_' + MEMBER_ID,
             'weight': 1, 'ip_address': MEMBER_ADDRESS, 'port': 80}
LB_POOL_WITH_MEMBER = {
    "display_name": "httppool1",
    "description": "my http pool",
    "id": LB_POOL_ID,
    "algorithm": "ROUND_ROBIN",
    "members": [
        {
            "display_name": "http-member1",
            "ip_address": MEMBER_ADDRESS,
            "port": "80",
            "weight": "1",
            "admin_state": "ENABLED"
        }
    ]
}
HM_ID = 'hhh-mmm'
LB_MONITOR_ID = 'mmm-ddd'

HM_BINDING = {'loadbalancer_id': LB_ID,
              'pool_id': POOL_ID,
              'hm_id': HM_ID,
              'lb_monitor_id': LB_MONITOR_ID,
              'lb_pool_id': LB_POOL_ID}
L7POLICY_ID = 'l7policy-xxx'
LB_RULE_ID = 'lb-rule-xx'
L7RULE_ID = 'l7rule-111'
L7POLICY_BINDING = {'l7policy_id': L7POLICY_ID,
                    'lb_vs_id': LB_VS_ID,
                    'lb_rule_id': LB_RULE_ID}

FAKE_CERT = {'id': 'cert-xyz'}

SERVICE_STATUSES = {
    "virtual_servers": [{
        "virtual_server_id": LB_VS_ID,
        "status": "UP"
    }],
    "service_id": LB_SERVICE_ID,
    "service_status": "UP",
    "pools": [{
        "members": [{
            "port": "80",
            "ip_address": MEMBER_ADDRESS,
            "status": "DOWN"
        }],
        "pool_id": LB_POOL_ID,
        "status": "DOWN"
    }]
}

VS_STATUSES = {
    "results": [{
        "virtual_server_id": LB_VS_ID,
        "status": "UP"
    }]
}


class BaseTestEdgeLbaasV2(base.BaseTestCase):
    def _tested_entity(self):
        return None

    def setUp(self):
        super(BaseTestEdgeLbaasV2, self).setUp()

        self.context = context.get_admin_context()
        self.edge_driver = lb_driver_v2.EdgeLoadbalancerDriverV2()

        self.lbv2_driver = mock.Mock()
        self.core_plugin = mock.Mock()
        base_mgr.LoadbalancerBaseManager._lbv2_driver = self.lbv2_driver
        base_mgr.LoadbalancerBaseManager._core_plugin = self.core_plugin
        self._patch_lb_plugin(self.lbv2_driver, self._tested_entity)
        self._patch_nsxlib_lb_clients(self.core_plugin)

        self.lb = lb_models.LoadBalancer(LB_ID, LB_TENANT_ID, 'lb1', '',
                                         'some-subnet', 'port-id', LB_VIP)
        self.listener = lb_models.Listener(LISTENER_ID, LB_TENANT_ID,
                                           'listener1', 'Dummy', None, LB_ID,
                                           'HTTP', protocol_port=80,
                                           loadbalancer=self.lb)
        self.https_listener = lb_models.Listener(
            LISTENER_ID, LB_TENANT_ID, 'listener1', '', None, LB_ID,
            'HTTPS', protocol_port=443, loadbalancer=self.lb)
        self.terminated_https_listener = lb_models.Listener(
            LISTENER_ID, LB_TENANT_ID, 'listener1', '', None, LB_ID,
            'TERMINATED_HTTPS', protocol_port=443, loadbalancer=self.lb)
        self.pool = lb_models.Pool(POOL_ID, LB_TENANT_ID, 'pool1', '',
                                   None, 'HTTP', 'ROUND_ROBIN',
                                   loadbalancer_id=LB_ID,
                                   listener=self.listener,
                                   listeners=[self.listener],
                                   loadbalancer=self.lb)
        self.member = lb_models.Member(MEMBER_ID, LB_TENANT_ID, POOL_ID,
                                       MEMBER_ADDRESS, 80, 1, pool=self.pool,
                                       name='member1')
        self.hm = lb_models.HealthMonitor(HM_ID, LB_TENANT_ID, 'PING', 3, 3,
                                          1, pool=self.pool, name='hm1')
        self.hm_http = lb_models.HealthMonitor(HM_ID, LB_TENANT_ID, 'HTTP',
                                               3, 3, 1, pool=self.pool,
                                               http_method='GET',
                                               url_path="/meh", name='hm2')

        self.l7policy = lb_models.L7Policy(L7POLICY_ID, LB_TENANT_ID,
                                           name='policy-test',
                                           description='policy-desc',
                                           listener_id=LISTENER_ID,
                                           action='REDIRECT_TO_POOL',
                                           redirect_pool_id=POOL_ID,
                                           listener=self.listener,
                                           position=1)
        self.l7rule = lb_models.L7Rule(L7RULE_ID, LB_TENANT_ID,
                                       l7policy_id=L7POLICY_ID,
                                       compare_type='EQUAL_TO',
                                       invert=False,
                                       type='HEADER',
                                       key='key1',
                                       value='val1',
                                       policy=self.l7policy)

    def tearDown(self):
        self._unpatch_lb_plugin(self.lbv2_driver, self._tested_entity)
        super(BaseTestEdgeLbaasV2, self).tearDown()

    def _patch_lb_plugin(self, lb_plugin, manager):
        self.real_manager = getattr(lb_plugin, manager)
        lb_manager = mock.patch.object(lb_plugin, manager).start()
        mock.patch.object(lb_manager, 'create').start()
        mock.patch.object(lb_manager, 'update').start()
        mock.patch.object(lb_manager, 'delete').start()
        mock.patch.object(lb_manager, 'successful_completion').start()

    def _patch_nsxlib_lb_clients(self, core_plugin):
        nsxlib = mock.patch.object(core_plugin, 'nsxlib').start()
        load_balancer = mock.patch.object(nsxlib, 'load_balancer').start()
        self.service_client = mock.patch.object(load_balancer,
                                                'service').start()
        self.app_client = mock.patch.object(load_balancer,
                                            'application_profile').start()
        self.vs_client = mock.patch.object(load_balancer,
                                           'virtual_server').start()
        self.pool_client = mock.patch.object(load_balancer,
                                             'pool').start()
        self.monitor_client = mock.patch.object(load_balancer,
                                                'monitor').start()
        self.rule_client = mock.patch.object(load_balancer,
                                             'rule').start()
        self.tm_client = mock.patch.object(nsxlib,
                                           'trust_management').start()

    def _unpatch_lb_plugin(self, lb_plugin, manager):
        setattr(lb_plugin, manager, self.real_manager)


class TestEdgeLbaasV2Loadbalancer(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2Loadbalancer, self).setUp()

    @property
    def _tested_entity(self):
        return 'load_balancer'

    def test_create(self):
        with mock.patch.object(lb_utils, 'validate_lb_subnet'
                               ) as mock_validate_lb_subnet:
            mock_validate_lb_subnet.return_value = True

            self.edge_driver.loadbalancer.create(self.context, self.lb)

            mock_successful_completion = (
                self.lbv2_driver.load_balancer.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.lb,
                                                          delete=False)

    def test_update(self):
        new_lb = lb_models.LoadBalancer(LB_ID, 'yyy-yyy', 'lb1-new',
                                        'new-description', 'some-subnet',
                                        'port-id', LB_VIP)

        self.edge_driver.loadbalancer.update(self.context, self.lb, new_lb)

        mock_successful_completion = (
            self.lbv2_driver.load_balancer.successful_completion)
        mock_successful_completion.assert_called_with(self.context, new_lb,
                                                      delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                               ) as mock_get_lb_binding, \
            mock.patch.object(self.service_client, 'get'
                              ) as mock_get_lb_service, \
            mock.patch.object(self.service_client, 'delete'
                              ) as mock_delete_lb_service, \
            mock.patch.object(nsx_db, 'delete_nsx_lbaas_loadbalancer_binding'
                              ) as mock_delete_lb_binding:
            mock_get_lb_binding.return_value = LB_BINDING
            mock_get_lb_service.return_value = {'id': LB_SERVICE_ID}

            self.edge_driver.loadbalancer.delete(self.context, self.lb)

            mock_delete_lb_service.assert_called_with(LB_SERVICE_ID)
            mock_delete_lb_binding.assert_called_with(
                self.context.session, LB_ID)
            mock_successful_completion = (
                self.lbv2_driver.load_balancer.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.lb,
                                                          delete=True)

    def test_stats(self):
        pass

    def test_refresh(self):
        pass

    def test_status_update(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                               ) as mock_get_lb_binding, \
            mock.patch.object(self.service_client, 'get_status'
                              ) as mock_get_lb_service_status, \
            mock.patch.object(self.service_client, 'get_virtual_servers_status'
                              ) as mock_get_vs_status, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding_by_lb_pool'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.pool_client, 'get'
                              ) as mock_get_pool, \
            mock.patch.object(nsx_db,
                              'get_nsx_lbaas_listener_binding_by_lb_and_vs'
                              ) as mock_get_listener_binding:
            mock_get_lb_binding.return_value = LB_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_listener_binding.return_value = LISTENER_BINDING
            mock_get_lb_service_status.return_value = SERVICE_STATUSES
            mock_get_vs_status.return_value = VS_STATUSES
            mock_get_pool.return_value = LB_POOL_WITH_MEMBER
            statuses = self.edge_driver.loadbalancer.get_operating_status(
                self.context, self.lb.id, with_members=True)
            self.assertEqual(1, len(statuses['loadbalancers']))
            self.assertEqual('ONLINE', statuses['loadbalancers'][0]['status'])
            self.assertEqual(1, len(statuses['pools']))
            self.assertEqual('OFFLINE', statuses['pools'][0]['status'])
            self.assertEqual(1, len(statuses['listeners']))
            self.assertEqual('ONLINE', statuses['listeners'][0]['status'])
            self.assertEqual(1, len(statuses['members']))
            self.assertEqual('OFFLINE', statuses['members'][0]['status'])


class TestEdgeLbaasV2Listener(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2Listener, self).setUp()

    @property
    def _tested_entity(self):
        return 'listener'

    def _create_listener(self, protocol='HTTP'):
        with mock.patch.object(self.core_plugin, 'get_floatingips'
                               ) as mock_get_floatingips, \
            mock.patch.object(self.app_client, 'create'
                              ) as mock_create_app_profile, \
            mock.patch.object(self.vs_client, 'create'
                              ) as mock_create_virtual_server, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(self.service_client, 'add_virtual_server'
                              ) as mock_add_virtual_server, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_listener_binding'
                              ) as mock_add_listener_binding:
            mock_get_floatingips.return_value = []
            mock_create_app_profile.return_value = {'id': APP_PROFILE_ID}
            mock_create_virtual_server.return_value = {'id': LB_VS_ID}
            mock_get_lb_binding.return_value = LB_BINDING
            listener = self.listener
            if protocol == 'HTTPS':
                listener = self.https_listener

            self.edge_driver.listener.create(self.context, listener)

            mock_add_virtual_server.assert_called_with(LB_SERVICE_ID,
                                                       LB_VS_ID)
            mock_add_listener_binding.assert_called_with(
                self.context.session, LB_ID, LISTENER_ID, APP_PROFILE_ID,
                LB_VS_ID)

            mock_successful_completion = (
                self.lbv2_driver.listener.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          listener,
                                                          delete=False)

    def test_create_http_listener(self):
        self._create_listener()

    def test_create_https_listener(self):
        self._create_listener(protocol='HTTPS')

    def test_create_terminated_https(self):
        with mock.patch.object(self.core_plugin, 'get_floatingips'
                               ) as mock_get_floatingips, \
            mock.patch.object(self.tm_client, 'create_cert'
                              ) as mock_create_cert, \
            mock.patch.object(self.app_client, 'create'
                              ) as mock_create_app_profile, \
            mock.patch.object(self.vs_client, 'create'
                              ) as mock_create_virtual_server, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(self.service_client, 'add_virtual_server'
                              ) as mock_add_virtual_server, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_listener_binding'
                              ) as mock_add_listener_binding:
            mock_get_floatingips.return_value = []
            mock_create_cert.return_value = FAKE_CERT['id']
            mock_create_app_profile.return_value = {'id': APP_PROFILE_ID}
            mock_create_virtual_server.return_value = {'id': LB_VS_ID}
            mock_get_lb_binding.return_value = LB_BINDING

            self.edge_driver.listener.create(self.context,
                                             self.terminated_https_listener)
            mock_add_virtual_server.assert_called_with(LB_SERVICE_ID,
                                                       LB_VS_ID)
            mock_add_listener_binding.assert_called_with(
                self.context.session, LB_ID, LISTENER_ID, APP_PROFILE_ID,
                LB_VS_ID)

            mock_successful_completion = (
                self.lbv2_driver.listener.successful_completion)
            mock_successful_completion.assert_called_with(
                self.context, self.terminated_https_listener,
                delete=False)

    def test_update(self):
        new_listener = lb_models.Listener(LISTENER_ID, LB_TENANT_ID,
                                          'listener1-new', 'new-description',
                                          None, LB_ID, protocol_port=80,
                                          loadbalancer=self.lb)
        with mock.patch.object(self.core_plugin, 'get_floatingips'
                               ) as mock_get_floatingips, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_listener_binding'
                              ) as mock_get_listener_binding:
            mock_get_floatingips.return_value = []
            mock_get_listener_binding.return_value = LISTENER_BINDING

            self.edge_driver.listener.update(self.context, self.listener,
                                             new_listener)

            mock_successful_completion = (
                self.lbv2_driver.listener.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          new_listener,
                                                          delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_listener_binding'
                               ) as mock_get_listener_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(self.service_client, 'get'
                              ) as mock_get_lb_service, \
            mock.patch.object(self.service_client, 'remove_virtual_server'
                              ) as mock_remove_virtual_server, \
            mock.patch.object(self.app_client, 'delete'
                              ) as mock_delete_app_profile, \
            mock.patch.object(self.vs_client, 'delete'
                              ) as mock_delete_virtual_server, \
            mock.patch.object(nsx_db, 'delete_nsx_lbaas_listener_binding',
                              ) as mock_delete_listener_binding:
            mock_get_listener_binding.return_value = LISTENER_BINDING
            mock_get_lb_binding.return_value = LB_BINDING
            mock_get_lb_service.return_value = {
                'id': LB_SERVICE_ID,
                'virtual_server_ids': [LB_VS_ID]}

            self.edge_driver.listener.delete(self.context, self.listener)

            mock_remove_virtual_server.assert_called_with(LB_SERVICE_ID,
                                                          LB_VS_ID)
            mock_delete_virtual_server.assert_called_with(LB_VS_ID)
            mock_delete_app_profile.assert_called_with(APP_PROFILE_ID)

            mock_delete_listener_binding.assert_called_with(
                self.context.session, LB_ID, LISTENER_ID)

            mock_successful_completion = (
                self.lbv2_driver.listener.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.listener,
                                                          delete=True)


class TestEdgeLbaasV2Pool(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2Pool, self).setUp()

    @property
    def _tested_entity(self):
        return 'pool'

    def test_create(self):
        with mock.patch.object(self.pool_client, 'create'
                               ) as mock_create_pool, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_pool_binding'
                              ) as mock_add_pool_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_listener_binding'
                              ) as mock_get_listener_binding, \
            mock.patch.object(self.vs_client, 'update', return_value=None), \
            mock.patch.object(nsx_db, 'update_nsx_lbaas_pool_binding'
                              ) as mock_update_pool_binding:
            mock_create_pool.return_value = {'id': LB_POOL_ID}
            mock_get_listener_binding.return_value = LISTENER_BINDING

            self.edge_driver.pool.create(self.context, self.pool)

            mock_add_pool_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID, LB_POOL_ID)
            mock_update_pool_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID, LB_VS_ID)
            mock_successful_completion = (
                self.lbv2_driver.pool.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.pool,
                                                          delete=False)

    def test_update(self):
        new_pool = lb_models.Pool(POOL_ID, LB_TENANT_ID, 'pool-name', '',
                                  None, 'HTTP', 'LEAST_CONNECTIONS',
                                  listener=self.listener)
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                               ) as mock_get_pool_binding:
            mock_get_pool_binding.return_value = POOL_BINDING

            self.edge_driver.pool.update(self.context, self.pool, new_pool)

            mock_successful_completion = (
                self.lbv2_driver.pool.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          new_pool,
                                                          delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                               ) as mock_get_pool_binding, \
            mock.patch.object(self.vs_client, 'update', return_value=None
                              ) as mock_update_virtual_server, \
            mock.patch.object(self.pool_client, 'delete'
                              ) as mock_delete_pool, \
            mock.patch.object(nsx_db, 'delete_nsx_lbaas_pool_binding'
                              ) as mock_delete_pool_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding:
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_lb_binding.return_value = None

            self.edge_driver.pool.delete(self.context, self.pool)

            mock_update_virtual_server.assert_called_with(LB_VS_ID,
                                                          pool_id='')
            mock_delete_pool.assert_called_with(LB_POOL_ID)
            mock_delete_pool_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID)

            mock_successful_completion = (
                self.lbv2_driver.pool.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.pool,
                                                          delete=True)


class TestEdgeLbaasV2Member(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2Member, self).setUp()

    @property
    def _tested_entity(self):
        return 'member'

    def _test_create(self, lb_binding, pool_binding):
        with mock.patch.object(lb_utils, 'validate_lb_member_subnet'
                               ) as mock_validate_lb_subnet, \
            mock.patch.object(self.lbv2_driver.plugin, 'get_pool_members'
                              ) as mock_get_pool_members, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network, \
            mock.patch.object(lb_utils, 'get_router_from_network'
                              ) as mock_get_router, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(nsx_db, 'get_nsx_router_id'
                              ) as mock_get_nsx_router_id, \
            mock.patch.object(self.service_client, 'get_router_lb_service'
                              ) as mock_get_lb_service, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_loadbalancer_binding'
                              ) as mock_add_loadbalancer_binding, \
            mock.patch.object(self.service_client,
                              'add_virtual_server'
                              ) as mock_add_vs_to_service, \
            mock.patch.object(self.pool_client, 'get'
                              ) as mock_get_pool, \
            mock.patch.object(self.pool_client, 'update_pool_with_members'
                              ) as mock_update_pool_with_members:
            mock_validate_lb_subnet.return_value = True
            mock_get_pool_members.return_value = [self.member]
            mock_get_network.return_value = LB_NETWORK
            mock_get_router.return_value = LB_ROUTER_ID
            mock_get_pool_binding.return_value = pool_binding
            mock_get_lb_binding.return_value = lb_binding
            mock_get_nsx_router_id.return_value = LB_ROUTER_ID
            mock_get_lb_service.return_value = {'id': LB_SERVICE_ID}
            mock_get_pool.return_value = LB_POOL

            self.edge_driver.member.create(self.context, self.member)
            if not lb_binding:
                mock_add_loadbalancer_binding.assert_called_with(
                    self.context.session, LB_ID, LB_SERVICE_ID, LB_ROUTER_ID,
                    LB_VIP)
            else:
                mock_add_loadbalancer_binding.assert_not_called()
            mock_add_vs_to_service.assert_called_with(LB_SERVICE_ID, LB_VS_ID)
            mock_update_pool_with_members.assert_called_with(LB_POOL_ID,
                                                             [LB_MEMBER])
            mock_successful_completion = (
                self.lbv2_driver.member.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.member,
                                                          delete=False)

    def test_create(self):
        self._test_create(None, POOL_BINDING)

    def test_create_existing_binding(self):
        self._test_create(LB_BINDING, POOL_BINDING)

    def test_create_with_service(self):
        ext_cidr = '1.1.1.0/24'
        with mock.patch.object(lb_utils, 'validate_lb_member_subnet'
                               ) as mock_validate_lb_subnet, \
            mock.patch.object(self.lbv2_driver.plugin, 'get_pool_members'
                              ) as mock_get_pool_members, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network, \
            mock.patch.object(lb_utils, 'get_router_from_network'
                              ) as mock_get_router, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(nsx_db, 'get_nsx_router_id'
                              ) as mock_get_nsx_router_id, \
            mock.patch.object(self.service_client, 'get_router_lb_service'
                              ) as mock_get_lb_service, \
            mock.patch.object(self.service_client, 'create'
                              ) as mock_create_lb_service, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_loadbalancer_binding'
                              ) as mock_add_loadbalancer_bidning, \
            mock.patch.object(self.service_client,
                              'add_virtual_server'
                              ) as mock_add_vs_to_service, \
            mock.patch.object(self.pool_client, 'get'
                              ) as mock_get_pool, \
            mock.patch.object(self.pool_client, 'update_pool_with_members'
                              ) as mock_update_pool_with_members,\
            mock.patch.object(self.core_plugin.nsxlib.logical_router,
                              'update_advertisement_rules') as update_adv,\
            mock.patch.object(self.core_plugin, '_find_router_gw_subnets'
                              ) as mock_get_subnets,\
            mock.patch.object(self.core_plugin, 'get_router'
                              ) as mock_core_get_router:
            mock_validate_lb_subnet.return_value = True
            mock_get_pool_members.return_value = [self.member]
            mock_get_network.return_value = LB_NETWORK
            mock_get_router.return_value = LB_ROUTER_ID
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_lb_binding.return_value = None
            mock_get_nsx_router_id.return_value = LB_ROUTER_ID
            mock_get_lb_service.return_value = {}
            mock_create_lb_service.return_value = {'id': LB_SERVICE_ID}
            mock_get_pool.return_value = LB_POOL
            mock_core_get_router.return_value = {
                'id': LB_ROUTER_ID,
                'name': 'router1',
                'external_gateway_info': 'dummy'}
            mock_get_subnets.return_value = [{'cidr': ext_cidr}]

            self.edge_driver.member.create(self.context, self.member)

            mock_add_loadbalancer_bidning.assert_called_with(
                self.context.session, LB_ID, LB_SERVICE_ID, LB_ROUTER_ID,
                LB_VIP)
            mock_add_vs_to_service.assert_called_with(LB_SERVICE_ID, LB_VS_ID)
            mock_update_pool_with_members.assert_called_with(LB_POOL_ID,
                                                             [LB_MEMBER])
            update_adv.assert_called_with(
                LB_ROUTER_ID,
                [{'networks': [ext_cidr],
                  'display_name': lb_utils.ADV_RULE_NAME,
                  'rule_filter': {'match_route_types': ['T1_LB_VIP'],
                  'prefix_operator': 'EQ'},
                  'action': 'ALLOW'}],
                name_prefix=lb_utils.ADV_RULE_NAME)
            mock_successful_completion = (
                self.lbv2_driver.member.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.member,
                                                          delete=False)

    def test_create_lbs_no_router_gateway(self):
        with mock.patch.object(lb_utils, 'validate_lb_member_subnet'
                               ) as mock_validate_lb_subnet, \
            mock.patch.object(self.lbv2_driver.plugin, 'get_pool_members'
                              ) as mock_get_pool_members, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network, \
            mock.patch.object(lb_utils, 'get_router_from_network'
                              ) as mock_get_router_from_network, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_loadbalancer_binding'
                              ) as mock_get_lb_binding, \
            mock.patch.object(nsx_db, 'get_nsx_router_id'
                              ) as mock_get_nsx_router_id, \
            mock.patch.object(self.service_client, 'get_router_lb_service'
                              ) as mock_get_lb_service, \
            mock.patch.object(self.core_plugin, 'get_router'
                              ) as mock_get_router:
            mock_validate_lb_subnet.return_value = True
            mock_get_pool_members.return_value = [self.member]
            mock_get_network.return_value = LB_NETWORK
            mock_get_router_from_network.return_value = LB_ROUTER_ID
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_lb_binding.return_value = None
            mock_get_nsx_router_id.return_value = LB_ROUTER_ID
            mock_get_lb_service.return_value = None
            mock_get_router.return_value = {'id': 'router1-xxx'}

            self.assertRaises(n_exc.BadRequest,
                              self.edge_driver.member.create,
                              self.context,
                              self.member)

    def test_create_member_different_router(self):
        with mock.patch.object(self.lbv2_driver.plugin, 'get_pool_members'
                               ) as mock_get_pool_members, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network, \
            mock.patch.object(lb_utils, 'get_router_from_network'
                              ) as mock_get_router:
            mock_get_pool_members.return_value = [self.member]
            mock_get_network.return_value = LB_NETWORK
            mock_get_router.return_value = None

            self.assertRaises(n_exc.BadRequest,
                              self.edge_driver.member.create,
                              self.context,
                              self.member)

    def test_update(self):
        new_member = lb_models.Member(MEMBER_ID, LB_TENANT_ID, POOL_ID,
                                      MEMBER_ADDRESS, 80, 2, pool=self.pool,
                                      name='member-nnn-nnn')
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                               ) as mock_get_pool_binding, \
            mock.patch.object(self.pool_client, 'get'
                              ) as mock_get_pool, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network_from_subnet:
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_pool.return_value = LB_POOL_WITH_MEMBER
            mock_get_network_from_subnet.return_value = LB_NETWORK

            self.edge_driver.member.update(self.context, self.member,
                                           new_member)

            mock_successful_completion = (
                self.lbv2_driver.member.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          new_member,
                                                          delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                               ) as mock_get_pool_binding, \
            mock.patch.object(self.pool_client, 'get'
                              ) as mock_get_pool, \
            mock.patch.object(lb_utils, 'get_network_from_subnet'
                              ) as mock_get_network_from_subnet, \
            mock.patch.object(self.pool_client, 'update_pool_with_members'
                              ) as mock_update_pool_with_members:
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_pool.return_value = LB_POOL_WITH_MEMBER
            mock_get_network_from_subnet.return_value = LB_NETWORK

            self.edge_driver.member.delete(self.context, self.member)

            mock_update_pool_with_members.assert_called_with(LB_POOL_ID, [])

            mock_successful_completion = (
                self.lbv2_driver.member.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.member,
                                                          delete=True)


class TestEdgeLbaasV2HealthMonitor(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2HealthMonitor, self).setUp()

    @property
    def _tested_entity(self):
        return 'health_monitor'

    def test_create(self):
        with mock.patch.object(self.monitor_client, 'create'
                               ) as mock_create_monitor, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.pool_client, 'add_monitor_to_pool'
                              ) as mock_add_monitor_to_pool, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_monitor_binding'
                              ) as mock_add_monitor_binding:
            mock_create_monitor.return_value = {'id': LB_MONITOR_ID}
            mock_get_pool_binding.return_value = POOL_BINDING

            self.edge_driver.healthmonitor.create(self.context, self.hm)

            mock_add_monitor_to_pool.assert_called_with(LB_POOL_ID,
                                                        LB_MONITOR_ID)
            mock_add_monitor_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID, HM_ID, LB_MONITOR_ID,
                LB_POOL_ID)

            mock_successful_completion = (
                self.lbv2_driver.health_monitor.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.hm,
                                                          delete=False)

    def test_create_http(self):
        with mock.patch.object(self.monitor_client, 'create'
                               ) as mock_create_monitor, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.pool_client, 'add_monitor_to_pool'
                              ) as mock_add_monitor_to_pool, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_monitor_binding'
                              ) as mock_add_monitor_binding:
            mock_create_monitor.return_value = {'id': LB_MONITOR_ID}
            mock_get_pool_binding.return_value = POOL_BINDING

            # Verify HTTP-specific  monitor parameters are added
            self.edge_driver.healthmonitor.create(self.context, self.hm_http)
            self.assertEqual(1, len(mock_create_monitor.mock_calls))
            kw_args = mock_create_monitor.mock_calls[0][2]
            self.assertEqual(self.hm_http.http_method,
                             kw_args.get('request_method'))
            self.assertEqual(self.hm_http.url_path,
                             kw_args.get('request_url'))
            mock_add_monitor_to_pool.assert_called_with(LB_POOL_ID,
                                                        LB_MONITOR_ID)
            mock_add_monitor_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID, HM_ID, LB_MONITOR_ID,
                LB_POOL_ID)

            mock_successful_completion = (
                self.lbv2_driver.health_monitor.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.hm_http,
                                                          delete=False)

    def test_update(self):
        with mock.patch.object(self.monitor_client, 'update'
                               ) as mock_update_monitor, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_monitor_binding'
                              ) as mock_get_monitor_binding:
            mock_get_monitor_binding.return_value = HM_BINDING
            new_hm = lb_models.HealthMonitor(
                HM_ID, LB_TENANT_ID, 'PING', 5, 5,
                5, pool=self.pool, name='new_name')
            self.edge_driver.healthmonitor.update(
                self.context, self.hm, new_hm)
            mock_update_monitor.assert_called_with(
                LB_MONITOR_ID, display_name=mock.ANY,
                fall_count=5, interval=5, timeout=5,
                resource_type='LbIcmpMonitor')

            mock_successful_completion = (
                self.lbv2_driver.health_monitor.successful_completion)
            mock_successful_completion.assert_called_with(self.context, new_hm,
                                                          delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_monitor_binding'
                               ) as mock_get_monitor_binding, \
            mock.patch.object(self.pool_client, 'remove_monitor_from_pool'
                              ) as mock_remove_monitor_from_pool, \
            mock.patch.object(self.monitor_client, 'delete'
                              ) as mock_delete_monitor, \
            mock.patch.object(nsx_db, 'delete_nsx_lbaas_monitor_binding'
                              ) as mock_delete_monitor_binding:
            mock_get_monitor_binding.return_value = HM_BINDING

            self.edge_driver.healthmonitor.delete(self.context, self.hm)

            mock_remove_monitor_from_pool.assert_called_with(LB_POOL_ID,
                                                             LB_MONITOR_ID)
            mock_delete_monitor.assert_called_with(LB_MONITOR_ID)
            mock_delete_monitor_binding.assert_called_with(
                self.context.session, LB_ID, POOL_ID, HM_ID)

            mock_successful_completion = (
                self.lbv2_driver.health_monitor.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.hm,
                                                          delete=True)


class TestEdgeLbaasV2L7Policy(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2L7Policy, self).setUp()

    @property
    def _tested_entity(self):
        return 'l7policy'

    def test_create(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_listener_binding'
                               ) as mock_get_listener_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.rule_client, 'create'
                              ) as mock_create_rule, \
            mock.patch.object(self.vs_client, 'get'
                              ) as mock_get_virtual_server, \
            mock.patch.object(self.vs_client, 'update'
                              ) as mock_update_virtual_server, \
            mock.patch.object(nsx_db, 'add_nsx_lbaas_l7policy_binding'
                              ) as mock_add_l7policy_binding:
            mock_get_listener_binding.return_value = LISTENER_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_create_rule.return_value = {'id': LB_RULE_ID}
            mock_get_virtual_server.return_value = {'id': LB_VS_ID}

            self.edge_driver.l7policy.create(self.context, self.l7policy)

            mock_update_virtual_server.assert_called_with(
                LB_VS_ID, rule_ids=[LB_RULE_ID])
            mock_add_l7policy_binding.assert_called_with(
                self.context.session, L7POLICY_ID, LB_RULE_ID, LB_VS_ID)
            mock_successful_completion = (
                self.lbv2_driver.l7policy.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.l7policy,
                                                          delete=False)

    def test_update(self):
        new_l7policy = lb_models.L7Policy(L7POLICY_ID, LB_TENANT_ID,
                                          name='new-policy',
                                          listener_id=LISTENER_ID,
                                          action='REJECT',
                                          listener=self.listener,
                                          position=2)
        vs_with_rules = {
            'id': LB_VS_ID,
            'rule_ids': [LB_RULE_ID, 'abc', 'xyz']
        }
        rule_body = {
            'match_conditions': [],
            'actions': [{
                'type': 'LbHttpRejectAction',
                'reply_status': '403'}],
            'phase': 'HTTP_FORWARDING',
            'match_strategy': 'ALL'
        }
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_l7policy_binding'
                               ) as mock_get_l7policy_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.rule_client, 'update'
                              ) as mock_update_rule, \
            mock.patch.object(self.vs_client, 'get'
                              ) as mock_get_virtual_server, \
            mock.patch.object(self.vs_client, 'update'
                              ) as mock_update_virtual_server:
            mock_get_l7policy_binding.return_value = L7POLICY_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING
            mock_get_virtual_server.return_value = vs_with_rules

            self.edge_driver.l7policy.update(self.context, self.l7policy,
                                             new_l7policy)

            mock_update_rule.assert_called_with(LB_RULE_ID,
                                                **rule_body)
            mock_update_virtual_server.assert_called_with(
                LB_VS_ID, rule_ids=['abc', LB_RULE_ID, 'xyz'])
            mock_successful_completion = (
                self.lbv2_driver.l7policy.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          new_l7policy,
                                                          delete=False)

    def test_delete(self):
        with mock.patch.object(nsx_db, 'get_nsx_lbaas_l7policy_binding'
                               ) as mock_get_l7policy_binding, \
            mock.patch.object(self.vs_client, 'remove_rule'
                              ) as mock_vs_remove_rule, \
            mock.patch.object(self.rule_client, 'delete'
                              ) as mock_delete_rule, \
            mock.patch.object(nsx_db, 'delete_nsx_lbaas_l7policy_binding'
                              ) as mock_delete_l7policy_binding:
            mock_get_l7policy_binding.return_value = L7POLICY_BINDING

            self.edge_driver.l7policy.delete(self.context, self.l7policy)

            mock_vs_remove_rule.assert_called_with(LB_VS_ID, LB_RULE_ID)
            mock_delete_rule.assert_called_with(LB_RULE_ID)
            mock_delete_l7policy_binding.assert_called_with(
                self.context.session, L7POLICY_ID)
            mock_successful_completion = (
                self.lbv2_driver.l7policy.successful_completion)
            mock_successful_completion.assert_called_with(
                self.context, self.l7policy, delete=True)


class TestEdgeLbaasV2L7Rule(BaseTestEdgeLbaasV2):
    def setUp(self):
        super(TestEdgeLbaasV2L7Rule, self).setUp()

    @property
    def _tested_entity(self):
        return 'l7rule'

    def test_create(self):
        self.l7policy.rules = [self.l7rule]
        create_rule_body = {
            'match_conditions': [{
                'type': 'LbHttpRequestHeaderCondition',
                'match_type': 'EQUALS',
                'header_name': self.l7rule.key,
                'header_value': self.l7rule.value}],
            'actions': [{
                'type': 'LbSelectPoolAction',
                'pool_id': LB_POOL_ID}],
            'phase': 'HTTP_FORWARDING',
            'match_strategy': 'ALL'
        }

        with mock.patch.object(nsx_db, 'get_nsx_lbaas_l7policy_binding'
                               ) as mock_get_l7policy_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.rule_client, 'update'
                              ) as mock_update_rule:
            mock_get_l7policy_binding.return_value = L7POLICY_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING

            self.edge_driver.l7rule.create(self.context, self.l7rule)

            mock_update_rule.assert_called_with(LB_RULE_ID,
                                                **create_rule_body)

            mock_successful_completion = (
                self.lbv2_driver.l7rule.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.l7rule,
                                                          delete=False)

    def test_update(self):
        new_l7rule = lb_models.L7Rule(L7RULE_ID, LB_TENANT_ID,
                                      l7policy_id=L7POLICY_ID,
                                      compare_type='STARTS_WITH',
                                      invert=True,
                                      type='COOKIE',
                                      key='cookie1',
                                      value='xxxxx',
                                      policy=self.l7policy)
        self.l7policy.rules = [new_l7rule]
        update_rule_body = {
            'match_conditions': [{
                'type': 'LbHttpRequestHeaderCondition',
                'match_type': 'STARTS_WITH',
                'header_name': 'Cookie',
                'header_value': 'cookie1=xxxxx'}],
            'actions': [{
                'type': 'LbSelectPoolAction',
                'pool_id': LB_POOL_ID}],
            'phase': 'HTTP_FORWARDING',
            'match_strategy': 'ALL'
        }

        with mock.patch.object(nsx_db, 'get_nsx_lbaas_l7policy_binding'
                               ) as mock_get_l7policy_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.rule_client, 'update'
                              ) as mock_update_rule:
            mock_get_l7policy_binding.return_value = L7POLICY_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING

            self.edge_driver.l7rule.update(self.context, self.l7rule,
                                           new_l7rule)

            mock_update_rule.assert_called_with(LB_RULE_ID,
                                                **update_rule_body)

            mock_successful_completion = (
                self.lbv2_driver.l7rule.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          new_l7rule,
                                                          delete=False)

    def test_delete(self):
        self.l7policy.rules = [self.l7rule]
        delete_rule_body = {
            'match_conditions': [],
            'actions': [{
                'type': 'LbSelectPoolAction',
                'pool_id': LB_POOL_ID}],
            'phase': 'HTTP_FORWARDING',
            'match_strategy': 'ALL'
        }

        with mock.patch.object(nsx_db, 'get_nsx_lbaas_l7policy_binding'
                               ) as mock_get_l7policy_binding, \
            mock.patch.object(nsx_db, 'get_nsx_lbaas_pool_binding'
                              ) as mock_get_pool_binding, \
            mock.patch.object(self.rule_client, 'update'
                              ) as mock_update_rule:
            mock_get_l7policy_binding.return_value = L7POLICY_BINDING
            mock_get_pool_binding.return_value = POOL_BINDING

            self.edge_driver.l7rule.delete(self.context, self.l7rule)

            mock_update_rule.assert_called_with(LB_RULE_ID,
                                                **delete_rule_body)

            mock_successful_completion = (
                self.lbv2_driver.l7rule.successful_completion)
            mock_successful_completion.assert_called_with(self.context,
                                                          self.l7rule,
                                                          delete=True)
