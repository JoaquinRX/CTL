from odoo import api, models, fields
from enum import Enum
from odoo.exceptions import UserError


class ProjectType(Enum):
    WAREHOUSE = "Warehouse"
    GENERAL = "General"


PROJECT_WAREHOUSE_STAGES = {
    "Nuevo",
    "Pendiente retirar",
    "Pendiente recibir",
    "Mesa de entrada",
    "Pick",
    "Verificacion tecnica",
    "Mesa de envios",
    "En transito",
    "Finalizado",
}


class ProjectInherit(models.Model):
    _name = "project.project"
    _inherit = "project.project"

    rx_project_type = fields.Selection(
        [(type.value, type.value) for type in ProjectType],
        string="Type",
        required=True,
        default=ProjectType.GENERAL.value,
    )

    rx_is_warehouse = fields.Boolean(
        string="Is warehouse",
        compute="_compute_is_warehouse",
        readonly=True,
        store=True,
    )
    rx_warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse pair")

    rx_count_pending_withdrawal = fields.Char(
        string="Pending withdrawal", compute="_compute_count_pending_withdrawal"
    )
    rx_count_pending_receive = fields.Char(
        string="Pending receive", compute="_compute_count_pending_receive"
    )

    def _compute_count_pending_withdrawal(self):
        for project in self:
            if not project.rx_is_warehouse:
                project.rx_count_pending_withdrawal = ""
                continue
            count = len(
                self.env["project.task"].search(
                    [
                        ("project_id", "=", project.id),
                        ("stage_id.name", "=", "Pendiente retirar"),
                    ]
                )
            )
            project.rx_count_pending_withdrawal = f"Pendiente retirar: {count}"

    def _compute_count_pending_receive(self):
        for project in self:
            if not project.rx_is_warehouse:
                project.rx_count_pending_receive = ""
                continue
            count = len(
                self.env["project.task"].search(
                    [
                        ("project_id", "=", project.id),
                        ("stage_id.name", "=", "Pendiente recibir"),
                    ]
                )
            )
            project.rx_count_pending_receive = f"Pendiente recibir: {count}"

    @api.depends("rx_project_type")
    def _compute_is_warehouse(self):
        for project in self:
            project.rx_is_warehouse = (
                project.rx_project_type == ProjectType.WAREHOUSE.value
            )

    def write(self, values):
        result = super(ProjectInherit, self).write(values)

        if "rx_warehouse_id" in values:
            warehouses = self.env["stock.warehouse"].search([])
            warehouses.compute_linked_project()
        return result


class TaskInherit(models.Model):
    _name = "project.task"
    _inherit = "project.task"

    rx_project_type = fields.Selection(
        string="Type", related="project_id.rx_project_type"
    )
    rx_task_order_line_ids = fields.One2many(
        "project.task.order.line", "rx_task_id", string="Task Quants"
    )

    rx_is_sub_order = fields.Boolean(string="Is sub order", readonly=True)
    rx_sub_order_id = fields.Many2one("project.task", string="Sub order")
    rx_parent_order_id = fields.Many2one(
        "project.task", string="Parent order", readonly=True
    )

    rx_is_warehouse = fields.Boolean(
        string="Is warehouse", related="project_id.rx_is_warehouse", readonly=True
    )
    rx_warehouse_id = fields.Many2one(
        related="project_id.rx_warehouse_id", readonly=True
    )
    rx_stock_from_other_warehouse = fields.Boolean(string="Stock from other warehouse")
    rx_available_stock_ids = fields.Many2many("stock.quant")
    rx_total_count = fields.Integer(compute="_compute_total_count", string="Total:")

    rx_order_type = fields.Selection(
        [
            ("assets purchase", "Asset purchase"),
            ("returns", "Returns"),
            ("assets request", "Assets request"),
            ("re-stock deposit", "Re-stock deposit"),
        ],
        string="Order type",
    )

    rx_ticket = fields.Char(string="Ticket")
    rx_refund_type = fields.Selection(
        [
            ("home pick-up", "Home pick-up"),
            ("leave in deposit", "Leave in deposit"),
        ],
        string="Refund type",
    )

    rx_partner_id = fields.Many2one("res.partner", string="Origin")
    rx_direction = fields.Many2one("res.partner", string="Direction")
    rx_logistic = fields.Selection(
        [
            ("ctl logistic", "CTL Logistic"),
            ("osde logistic", "OSDE Logistic"),
            ("pick-up", "Pick-up"),
        ],
        string="Logistic",
    )

    rx_final_location = fields.Many2one("stock.location", string="Final location")
    rx_date_of_receipt = fields.Date(string="Estimated date of receipt")
    rx_provider = fields.Many2one("res.partner", string="Provider")
    rx_partner_address = fields.Char(
        "Address", related="rx_partner_id.contact_address", store=True
    )
    rx_origin_warehouse = fields.Many2one("stock.warehouse", string="Origin")
    rx_destination_warehouse = fields.Many2one("stock.warehouse", string="Destination")
    rx_multiple_locations = fields.Boolean(string="Multiple locations")
    rx_who_returns = fields.Selection(
        [
            ("crum", "CRUM"),
            ("node", "NODE"),
            ("user/collaborator", "User/Collaborator"),
        ],
        string="Who returns",
    )

    @api.onchange("rx_final_location")
    def _onchange_final_location(self):
        for line in self.rx_task_order_line_ids:
            line.rx_final_location = self.rx_final_location

    @api.onchange("rx_order_type")
    def _onchange_order_type(self):
        if self.rx_order_type == "assets request":
            location_origin = self.env["stock.location"].search(
                [("name", "=", "Customers"), ("usage", "=", "customer")], limit=1
            )
            self.rx_final_location = location_origin
        elif self.rx_order_type == "assets purchase":
            location_origin = self.env["stock.location"].search(
                [("name", "=", "Mesa de entrada"), ("location_id.name", "=", "PATAG")],
                limit=1,
            )
            self.rx_final_location = location_origin

    @api.onchange("rx_task_order_line_ids")
    def _onchange_task_order_line_ids(self):
        if not self.rx_order_type and len(self.rx_task_order_line_ids) > 0:
            raise UserError("Debe seleccionar el tipo de orden")
        if not self.rx_final_location:
            return

        if self.rx_task_order_line_ids:
            unique_locations = self.rx_task_order_line_ids.mapped("rx_final_location")
            if len(unique_locations) <= 1:
                for line in self.rx_task_order_line_ids:
                    line.rx_final_location = self.rx_final_location

    @api.onchange(
        "rx_order_type", "rx_who_returns", "rx_origin_warehouse", "rx_partner_id"
    )
    def _onchange_clear_task_order_line_ids(self):
        self.rx_task_order_line_ids = [(5, 0, 0)]

    @api.onchange(
        "rx_task_order_line_ids",
        "rx_order_type",
        "rx_who_returns",
        "rx_origin_warehouse",
        "rx_stock_from_other_warehouse",
        "rx_partner_id",
    )
    def _onchange_task_quant_ids(self):
        quant_model = self.env["stock.quant"]
        stock_quants = self.env["stock.quant"]

        order_type = self.rx_order_type
        who_returns = self.rx_who_returns
        warehouse_id = self.rx_warehouse_id.id

        if self.rx_stock_from_other_warehouse:
            stock_quants = quant_model.search([])

        elif order_type in ["re-stock deposit", "assets request"]:
            stock_quants = quant_model.search(
                [
                    ("location_id.warehouse_id", "=", warehouse_id),
                    ("location_id.usage", "!=", "transit"),
                    ("available_quantity", ">", 0),
                ]
            )

        elif order_type == "returns":
            if who_returns == "user/collaborator":
                stock_quants = quant_model.search(
                    [
                        ("location_id.usage", "=", "customer"),
                        ("available_quantity", ">", 0),
                        ("owner_id", "=", self.rx_partner_id.id),
                    ]
                )
            elif who_returns in ["crum", "node"]:
                stock_quants = quant_model.search(
                    [
                        ("location_id.warehouse_id", "=", self.rx_origin_warehouse.id),
                        ("available_quantity", ">", 0),
                    ]
                )

        self.rx_available_stock_ids = [(5, 0, 0)]
        self.rx_available_stock_ids = [(6, 0, stock_quants.ids)]

    @api.onchange("stage_id")
    def _onchange_stage_id_assets_request(self):  # noqa C901
        if self.rx_order_type == "assets request":
            #  change stage limitations
            if self._origin.stage_id.name == "Finalizado":
                raise UserError(
                    f"La orden ya esta en el estado {self._origin.stage_id.name}"
                )
            elif not self.check_available_quant():
                raise UserError(
                    "La cantidad seleccionada no puede ser mayor a la disponible"
                )
            elif self.stage_id.name == "Nuevo":
                if not self._origin.stage_id.name == "Pick":
                    raise UserError(
                        f"La orden no puede volver a el estado {self.stage_id.name}"
                    )
                else:
                    return
            elif self.stage_id.name == "Pick":
                return
            elif not self.check_all_lines_done():
                raise UserError(
                    "Todas las lineas tienen que estar confirmadas para poder continuar"
                )
            elif (
                self.stage_id.name == "Pendiente recibir"
                or self.stage_id.name == "Verificacion tecnica"
            ):
                raise UserError(
                    f"No puede pasar una orden de pedido de activos a la etapa de {self.stage_id.name}"
                )
            elif not self.check_all_lines_final_location():
                raise UserError("Todas las lineas tienen que tener una ubicacion final")

            # change stage logic
            if self.stage_id.name in [
                "Mesa de envios",
                "Pendiente retirar",
                "Mesa de entrada",
                "En transito",
            ]:

                def transfer_prod():
                    location_dest_id = self.env["stock.location"].search(
                        [
                            ("warehouse_id", "=", self.rx_warehouse_id.id),
                            ("usage", "=", "transit"),
                            ("name", "=", self.stage_id.name),
                        ],
                        limit=1,
                    )
                    if not location_dest_id:
                        location_dest_id = self.env["stock.location"].search(
                            [
                                ("warehouse_id", "=", self.rx_warehouse_id.id),
                                ("usage", "=", "transit"),
                            ],
                            limit=1,
                        )
                    for line in self.rx_task_order_line_ids:
                        self.transfer_stock(line, location_dest_id)
                        if line.rx_lot_ids:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", location_dest_id.id),
                                    ("lot_id", "in", line.rx_lot_ids.ids),
                                ],
                                limit=1,
                            )
                        else:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", location_dest_id.id),
                                ],
                                limit=1,
                            )
                        line.write({"rx_stock_quant_id": new_stock_quant.id})

                if self.stage_id.name == "Mesa de envios":
                    transfer_prod()
                    self._force_change_stage("Mesa de envios")

                if self.stage_id.name == "Pendiente retirar":
                    transfer_prod()
                    self._force_change_stage("Pendiente retirar")

                if self.stage_id.name == "Mesa de entrada":
                    transfer_prod()
                    self._force_change_stage("Mesa de entrada")

                if self.stage_id.name == "En transito":
                    transfer_prod()
                    self._force_change_stage("En transito")

            elif self.stage_id.name == "Finalizado":
                for line in self.rx_task_order_line_ids:
                    self.transfer_stock(line, line.rx_final_location)
                    if line.rx_lot_ids:
                        new_stock_quant = self.env["stock.quant"].search(
                            [
                                (
                                    "product_id",
                                    "=",
                                    line.rx_stock_quant_id.product_id.id,
                                ),
                                ("location_id", "=", line.rx_final_location.id),
                                ("lot_id", "in", line.rx_lot_ids.ids),
                            ],
                            limit=1,
                        )
                    else:
                        new_stock_quant = self.env["stock.quant"].search(
                            [
                                (
                                    "product_id",
                                    "=",
                                    line.rx_stock_quant_id.product_id.id,
                                ),
                                ("location_id", "=", line.rx_final_location.id),
                            ],
                            limit=1,
                        )
                    line.write({"rx_stock_quant_id": new_stock_quant.id})
                    self.assign_owner()
                self._force_change_stage("Finalizado")

    @api.onchange("stage_id")
    def _onchange_stage_id_returns(self):  # noqa: C901
        if self.rx_order_type == "returns":
            #  change stage limitations
            if self._origin.stage_id.name == "Finalizado":
                raise UserError(
                    f"La orden ya esta en el estado {self._origin.stage_id.name}"
                )
            elif not self.check_available_quant():
                raise UserError(
                    "La cantidad seleccionada no puede ser mayor a la disponible"
                )
            elif self.stage_id.name == "Nuevo":
                if not self._origin.stage_id.name == "Pick":
                    raise UserError(
                        f"La orden no puede volver a el estado {self.stage_id.name}"
                    )
                else:
                    return
            elif self.stage_id.name == "Pick":
                return
            elif not self.check_all_lines_done() and self.stage_id.name not in [
                "Pendiente retirar",
                "Mesa de envios",
            ]:
                raise UserError(
                    "Todas las lineas tienen que estar confirmadas para poder continuar"
                )
            elif not self.check_all_lines_final_location():
                raise UserError("Todas las lineas tienen que tener una ubicacion final")

            # change stage logic
            if self.rx_is_sub_order:
                if self.stage_id.name == "Finalizado":
                    print("sub-order finish")
                    # location_dest_id = self.env['stock.location'].search([('warehouse_id', '=', self.rx_parent_order_id.rx_warehouse_id.id), ('usage', '=', 'transit')], limit=1)
                    # for line in self.rx_task_order_line_ids:
                    #     self.transfer_stock(line, location_dest_id)
                    #     if line.rx_lot_ids:
                    #         new_stock_quant = self.env['stock.quant'].search([('product_id', '=', line.rx_stock_quant_id.product_id.id), ('location_id', '=', location_dest_id.id), ('lot_id', 'in', line.rx_lot_ids.ids)], limit=1)
                    #     else:
                    #         new_stock_quant = self.env['stock.quant'].search([('product_id', '=', line.rx_stock_quant_id.product_id.id), ('location_id', '=', location_dest_id.id)], limit=1)
                    #     line.write({'rx_stock_quant_id': new_stock_quant.id})

                    # self.rx_parent_order_id.write({'rx_task_order_line_ids': [(5, 0, 0)]})
                    # self.rx_parent_order_id.write({
                    #     'rx_task_order_line_ids': [(0, 0, {
                    #         'rx_task_id': self.rx_parent_order_id.id,
                    #         'rx_is_done': line.rx_is_done,
                    #         'rx_stock_quant_id': line.rx_stock_quant_id.id,
                    #         'rx_location_id': line.rx_location_id.id,
                    #         'rx_final_location': line.rx_final_location.id,
                    #         'rx_qty': line.rx_qty,
                    #         'rx_lot_ids': line.rx_lot_ids.ids
                    #     }) for line in self.rx_task_order_line_ids],
                    # })
                    # self._force_change_stage('Finalizado')

            else:  # is not sub-order
                if self.stage_id.name == "Finalizado":
                    self.unassign_owner()
                    for line in self.rx_task_order_line_ids:
                        self.transfer_stock(line, line.rx_final_location)
                        if line.rx_lot_ids:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", line.rx_final_location.id),
                                    ("lot_id", "in", line.rx_lot_ids.ids),
                                ],
                                limit=1,
                            )
                        else:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", line.rx_final_location.id),
                                ],
                                limit=1,
                            )
                        line.write({"rx_stock_quant_id": new_stock_quant.id})

                    if (
                        not self.rx_sub_order_id
                        and not self.rx_who_returns == "user/collaborator"
                    ):
                        raise UserError(
                            "No puede finalizar una orden sin antes crear una sub-orden"
                        )
                    self.rx_sub_order_id.write({"rx_task_order_line_ids": [(5, 0, 0)]})
                    self.rx_sub_order_id.write(
                        {
                            "rx_task_order_line_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "rx_task_id": self.rx_sub_order_id.id,
                                        "rx_is_done": line.rx_is_done,
                                        "rx_stock_quant_id": line.rx_stock_quant_id.id,
                                        "rx_location_id": line.rx_location_id.id,
                                        "rx_final_location": line.rx_final_location.id,
                                        "rx_qty": line.rx_qty,
                                        "rx_lot_ids": line.rx_lot_ids.ids,
                                    },
                                )
                                for line in self.rx_task_order_line_ids
                            ],
                        }
                    )
                    self._force_change_stage("Finalizado")

                if not self.rx_sub_order_id:
                    if (
                        self.stage_id.name
                        in [
                            "Mesa de envios",
                            "Pendiente retirar",
                            "Mesa de entrada",
                            "En transito",
                        ]
                        and not self.rx_who_returns == "user/collaborator"
                    ):
                        if not self.rx_origin_warehouse:
                            raise UserError("Debe seleccionar un almacén de destino")

                        def transfer_prod():
                            self.unassign_owner()
                            location_dest_id = self.env["stock.location"].search(
                                [
                                    ("warehouse_id", "=", self.rx_warehouse_id.id),
                                    ("usage", "=", "transit"),
                                    ("name", "=", self.stage_id.name),
                                ],
                                limit=1,
                            )
                            if not location_dest_id:
                                location_dest_id = self.env["stock.location"].search(
                                    [
                                        (
                                            "warehouse_id",
                                            "=",
                                            self.rx_origin_warehouse.id,
                                        ),
                                        ("usage", "=", "transit"),
                                    ],
                                    limit=1,
                                )
                            for line in self.rx_task_order_line_ids:
                                self.transfer_stock(line, location_dest_id)
                                if line.rx_lot_ids:
                                    new_stock_quant = self.env["stock.quant"].search(
                                        [
                                            (
                                                "product_id",
                                                "=",
                                                line.rx_stock_quant_id.product_id.id,
                                            ),
                                            ("location_id", "=", location_dest_id.id),
                                            ("lot_id", "in", line.rx_lot_ids.ids),
                                        ],
                                        limit=1,
                                    )
                                else:
                                    new_stock_quant = self.env["stock.quant"].search(
                                        [
                                            (
                                                "product_id",
                                                "=",
                                                line.rx_stock_quant_id.product_id.id,
                                            ),
                                            ("location_id", "=", location_dest_id.id),
                                        ],
                                        limit=1,
                                    )
                                line.write({"rx_stock_quant_id": new_stock_quant.id})

                            project_id = self.env["project.project"].search(
                                [("rx_warehouse_id", "=", self.rx_origin_warehouse.id)],
                                limit=1,
                            )
                            stage_id = self.env["project.task.type"].search(
                                [
                                    ("name", "=", "Nuevo"),
                                    ("project_ids", "in", [self.project_id.id]),
                                ],
                                limit=1,
                            )
                            sub_order_id = self.env["project.task"].create(
                                {
                                    "project_id": project_id.id,
                                    "name": f"{self.name} sub-orden",
                                    "stage_id": stage_id.id,
                                    "rx_is_sub_order": True,
                                    "rx_parent_order_id": self._origin.id,
                                    "rx_warehouse_id": self.rx_origin_warehouse.id,
                                    "rx_task_order_line_ids": [
                                        (
                                            0,
                                            0,
                                            {
                                                "rx_task_id": line.rx_task_id.id,
                                                "rx_stock_quant_id": line.rx_stock_quant_id.id,
                                                "rx_qty": line.rx_qty,
                                                "rx_location_id": line.rx_location_id.id,
                                                "rx_final_location": line.rx_final_location.id,
                                                "rx_is_done": line.rx_is_done,
                                                "rx_lot_ids": line.rx_lot_ids.ids,
                                            },
                                        )
                                        for line in self.rx_task_order_line_ids
                                    ],
                                    "rx_order_type": self.rx_order_type,
                                    "rx_who_returns": self.rx_who_returns,
                                    "rx_origin_warehouse": self.rx_origin_warehouse.id,
                                    "rx_destination_warehouse": self.rx_destination_warehouse.id,
                                    "rx_final_location": self.rx_final_location.id,
                                }
                            )
                            self.env["project.task"].search(
                                [("id", "=", self._origin.id)], limit=1
                            ).write({"rx_sub_order_id": sub_order_id.id})

                        if self.stage_id.name == "Mesa de envios":
                            transfer_prod()
                            self._force_change_stage("Mesa de envios")

                        if self.stage_id.name == "Pendiente retirar":
                            transfer_prod()
                            self._force_change_stage("Pendiente retirar")

                        if self.stage_id.name == "Mesa de entrada":
                            transfer_prod()
                            self._force_change_stage("Mesa de entrada")

                        if self.stage_id.name == "En transito":
                            transfer_prod()
                            self._force_change_stage("En transito")

                    elif (
                        self.stage_id.name in ["Mesa de entrada"]
                        and self.rx_who_returns == "user/collaborator"
                    ):
                        location_dest_id = self.env["stock.location"].search(
                            [
                                ("warehouse_id", "=", self.rx_warehouse_id.id),
                                ("usage", "=", "transit"),
                                ("name", "=", self.stage_id.name),
                            ],
                            limit=1,
                        )
                        if not location_dest_id:
                            location_dest_id = self.env["stock.location"].search(
                                [
                                    ("warehouse_id", "=", self.rx_warehouse_id.id),
                                    ("usage", "=", "transit"),
                                ],
                                limit=1,
                            )
                        self.unassign_owner()
                        for line in self.rx_task_order_line_ids:
                            self.transfer_stock(line, location_dest_id)
                            if line.rx_lot_ids:
                                new_stock_quant = self.env["stock.quant"].search(
                                    [
                                        (
                                            "product_id",
                                            "=",
                                            line.rx_stock_quant_id.product_id.id,
                                        ),
                                        ("location_id", "=", location_dest_id.id),
                                        ("lot_id", "in", line.rx_lot_ids.ids),
                                    ],
                                    limit=1,
                                )
                            else:
                                new_stock_quant = self.env["stock.quant"].search(
                                    [
                                        (
                                            "product_id",
                                            "=",
                                            line.rx_stock_quant_id.product_id.id,
                                        ),
                                        ("location_id", "=", location_dest_id.id),
                                    ],
                                    limit=1,
                                )
                            line.write({"rx_stock_quant_id": new_stock_quant.id})
                        self._force_change_stage("Mesa de entrada")

    @api.onchange("stage_id")
    def _onchange_stage_id_assets_purchase(self):  # noqa: C901
        if self.rx_order_type == "assets purchase":
            #  change stage limitations
            if self._origin.stage_id.name == "Finalizado":
                raise UserError(
                    f"La orden ya esta en el estado {self._origin.stage_id.name}"
                )
            elif self.stage_id.name == "Nuevo":
                if not self._origin.stage_id.name == "Pick":
                    raise UserError(
                        f"La orden no puede volver a el estado {self.stage_id.name}"
                    )
                else:
                    return
            elif self.stage_id.name == "Pick":
                return
            elif not self.check_all_lines_done() and self.stage_id.name not in [
                "Pendiente recibir",
                "Pendiente retirar",
                "Mesa de envios",
            ]:
                raise UserError(
                    "Todas las lineas tienen que estar confirmadas para poder continuar"
                )
            elif self.stage_id.name == "Verificacion tecnica":
                raise UserError(
                    f"No puede pasar una orden compra de activos a la etapa de {self.stage_id.name}"
                )
            elif not self.check_all_lines_final_location():
                raise UserError("Todas las lineas tienen que tener una ubicacion final")

            # change stage logic
            if self.stage_id.name in [
                "Mesa de envios",
                "Pendiente retirar",
                "Mesa de entrada",
                "En transito",
            ]:

                def transfer_prod():
                    location_origin = self.env["stock.location"].search(
                        [("name", "=", "Vendors"), ("usage", "=", "supplier")], limit=1
                    )
                    location_dest_id = self.env["stock.location"].search(
                        [
                            ("warehouse_id", "=", self.rx_warehouse_id.id),
                            ("usage", "=", "transit"),
                            ("name", "=", self.stage_id.name),
                        ],
                        limit=1,
                    )
                    if not location_dest_id:
                        location_dest_id = self.env["stock.location"].search(
                            [
                                ("warehouse_id", "=", self.rx_warehouse_id.id),
                                ("usage", "=", "transit"),
                            ],
                            limit=1,
                        )
                    for line in self.rx_task_order_line_ids:
                        if line.rx_stock_quant_id:
                            return
                        self.transfer_product(line, location_origin, location_dest_id)
                        if line.rx_lot_ids:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    ("product_id", "=", line.rx_product_id.id),
                                    ("location_id", "=", location_dest_id.id),
                                    ("lot_id", "in", line.rx_lot_ids.ids),
                                ],
                                limit=1,
                            )
                        else:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    ("product_id", "=", line.rx_product_id.id),
                                    ("location_id", "=", location_dest_id.id),
                                ],
                                limit=1,
                            )
                        line.write({"rx_stock_quant_id": new_stock_quant.id})

                if self.stage_id.name == "Mesa de envios":
                    transfer_prod()
                    self._force_change_stage("Mesa de envios")

                if self.stage_id.name == "Pendiente retirar":
                    transfer_prod()
                    self._force_change_stage("Pendiente retirar")

                if self.stage_id.name == "Mesa de entrada":
                    transfer_prod()
                    self._force_change_stage("Mesa de entrada")

                if self.stage_id.name == "En transito":
                    transfer_prod()
                    self._force_change_stage("En transito")

            elif self.stage_id.name == "Finalizado":
                for line in self.rx_task_order_line_ids:
                    self.transfer_stock(line, line.rx_final_location)
                    if line.rx_lot_ids:
                        new_stock_quant = self.env["stock.quant"].search(
                            [
                                (
                                    "product_id",
                                    "=",
                                    line.rx_stock_quant_id.product_id.id,
                                ),
                                ("location_id", "=", line.rx_final_location.id),
                                ("lot_id", "in", line.rx_lot_ids.ids),
                            ],
                            limit=1,
                        )
                    else:
                        new_stock_quant = self.env["stock.quant"].search(
                            [
                                (
                                    "product_id",
                                    "=",
                                    line.rx_stock_quant_id.product_id.id,
                                ),
                                ("location_id", "=", line.rx_final_location.id),
                            ],
                            limit=1,
                        )
                    line.write({"rx_stock_quant_id": new_stock_quant.id})
                self._force_change_stage("Finalizado")

    @api.onchange("stage_id")
    def _onchange_stage_id_re_stock_deposit(self):  # noqa: C901
        if self.rx_order_type == "re-stock deposit":
            #  change stage limitations
            if self._origin.stage_id.name == "Finalizado":
                raise UserError(
                    f"La orden ya esta en el estado {self._origin.stage_id.name}"
                )
            elif not self.check_available_quant():
                raise UserError(
                    "La cantidad seleccionada no puede ser mayor a la disponible"
                )
            elif self.stage_id.name == "Nuevo":
                if not self._origin.stage_id.name == "Pick":
                    raise UserError(
                        f"La orden no puede volver a el estado {self.stage_id.name}"
                    )
                else:
                    return
            elif self.stage_id.name == "Pick":
                return
            elif not self.check_all_lines_done():
                raise UserError(
                    "Todas las lineas tienen que estar confirmadas para poder continuar"
                )
            elif (
                self.stage_id.name == "Pendiente recibir"
                or self.stage_id.name == "Verificacion tecnica"
            ):
                raise UserError(
                    f"No puede pasar una orden de re-stock a la etapa de {self.stage_id.name}"
                )
            elif not self.check_all_lines_final_location():
                raise UserError("Todas las lineas tienen que tener una ubicacion final")
            elif not self.rx_destination_warehouse:
                raise UserError(
                    "Debe seleccionar un almacén de destino para crear la sub orden"
                )

            # change stage logic
            if self.rx_is_sub_order:
                if not self.stage_id.name == "Finalizado":
                    raise UserError("La sub-orden solo puede finalizarse")
                else:
                    for line in self.rx_task_order_line_ids:
                        self.transfer_stock(line, line.rx_final_location)
                        if line.rx_lot_ids:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", line.rx_final_location.id),
                                    ("lot_id", "in", line.rx_lot_ids.ids),
                                ],
                                limit=1,
                            )
                        else:
                            new_stock_quant = self.env["stock.quant"].search(
                                [
                                    (
                                        "product_id",
                                        "=",
                                        line.rx_stock_quant_id.product_id.id,
                                    ),
                                    ("location_id", "=", line.rx_final_location.id),
                                ],
                                limit=1,
                            )
                        line.write({"rx_stock_quant_id": new_stock_quant.id})

                    self.rx_parent_order_id.write(
                        {"rx_task_order_line_ids": [(5, 0, 0)]}
                    )
                    self.rx_parent_order_id.write(
                        {
                            "rx_task_order_line_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "rx_task_id": self.rx_parent_order_id.id,
                                        "rx_is_done": line.rx_is_done,
                                        "rx_stock_quant_id": line.rx_stock_quant_id.id,
                                        "rx_location_id": line.rx_location_id.id,
                                        "rx_final_location": line.rx_final_location.id,
                                        "rx_qty": line.rx_qty,
                                        "rx_lot_ids": line.rx_lot_ids.ids,
                                    },
                                )
                                for line in self.rx_task_order_line_ids
                            ],
                        }
                    )
                    self._force_change_stage("Finalizado")

            else:  # is not sub-order
                if not self.rx_sub_order_id:
                    if self.stage_id.name in [
                        "Mesa de envios",
                        "Pendiente retirar",
                        "Mesa de entrada",
                        "En transito",
                    ]:
                        if not self.rx_destination_warehouse:
                            raise UserError("Debe seleccionar un almacén de destino")

                        def transfer_prod():
                            location_dest_id = self.env["stock.location"].search(
                                [
                                    ("warehouse_id", "=", self.rx_warehouse_id.id),
                                    ("usage", "=", "transit"),
                                    ("name", "=", self.stage_id.name),
                                ],
                                limit=1,
                            )
                            if not location_dest_id:
                                location_dest_id = self.env["stock.location"].search(
                                    [
                                        ("warehouse_id", "=", self.rx_warehouse_id.id),
                                        ("usage", "=", "transit"),
                                    ],
                                    limit=1,
                                )
                            for line in self.rx_task_order_line_ids:
                                self.transfer_stock(line, location_dest_id)
                                if line.rx_lot_ids:
                                    new_stock_quant = self.env["stock.quant"].search(
                                        [
                                            (
                                                "product_id",
                                                "=",
                                                line.rx_stock_quant_id.product_id.id,
                                            ),
                                            ("location_id", "=", location_dest_id.id),
                                            ("lot_id", "in", line.rx_lot_ids.ids),
                                        ],
                                        limit=1,
                                    )
                                else:
                                    new_stock_quant = self.env["stock.quant"].search(
                                        [
                                            (
                                                "product_id",
                                                "=",
                                                line.rx_stock_quant_id.product_id.id,
                                            ),
                                            ("location_id", "=", location_dest_id.id),
                                        ],
                                        limit=1,
                                    )
                                line.write({"rx_stock_quant_id": new_stock_quant.id})

                            project_id = self.env["project.project"].search(
                                [
                                    (
                                        "rx_warehouse_id",
                                        "=",
                                        self.rx_destination_warehouse.id,
                                    )
                                ],
                                limit=1,
                            )
                            stage_id = self.env["project.task.type"].search(
                                [
                                    ("name", "=", "Pendiente recibir"),
                                    ("project_ids", "in", [self.project_id.id]),
                                ],
                                limit=1,
                            )
                            sub_order_id = self.env["project.task"].create(
                                {
                                    "project_id": project_id.id,
                                    "name": f"{self.name} sub-orden",
                                    "stage_id": stage_id.id,
                                    "rx_is_sub_order": True,
                                    "rx_parent_order_id": self._origin.id,
                                    "rx_warehouse_id": self.rx_destination_warehouse.id,
                                    "rx_destination_warehouse": self.rx_destination_warehouse.id,
                                    "rx_task_order_line_ids": [
                                        (
                                            0,
                                            0,
                                            {
                                                "rx_task_id": line.rx_task_id.id,
                                                "rx_stock_quant_id": line.rx_stock_quant_id.id,
                                                "rx_qty": line.rx_qty,
                                                "rx_location_id": line.rx_location_id.id,
                                                "rx_final_location": line.rx_final_location.id,
                                                "rx_is_done": line.rx_is_done,
                                                "rx_lot_ids": line.rx_lot_ids.ids,
                                            },
                                        )
                                        for line in self.rx_task_order_line_ids
                                    ],
                                    "rx_order_type": self.rx_order_type,
                                    "rx_who_returns": self.rx_who_returns,
                                    "rx_origin_warehouse": self.rx_origin_warehouse.id,
                                    "rx_final_location": self.rx_final_location.id,
                                }
                            )
                            self.env["project.task"].search(
                                [("id", "=", self._origin.id)], limit=1
                            ).write({"rx_sub_order_id": sub_order_id.id})

                        if self.stage_id.name == "Mesa de envios":
                            transfer_prod()
                            self._force_change_stage("Mesa de envios")

                        if self.stage_id.name == "Pendiente retirar":
                            transfer_prod()
                            self._force_change_stage("Pendiente retirar")

                        if self.stage_id.name == "Mesa de entrada":
                            transfer_prod()
                            self._force_change_stage("Mesa de entrada")

                        if self.stage_id.name == "En transito":
                            transfer_prod()
                            self._force_change_stage("En transito")

    def assign_owner(self):
        if not self.rx_partner_id:
            return

        for line in self.rx_task_order_line_ids:
            if line.rx_lot_ids:
                line.rx_stock_quant_id.write({"owner_id": self.rx_partner_id.id})
            else:
                old_quant = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", line.rx_stock_quant_id.product_id.id),
                        ("location_id", "=", line.rx_stock_quant_id.location_id.id),
                        ("owner_id", "=", False),
                    ],
                    limit=1,
                )
                if old_quant:
                    old_quant.write(
                        {"inventory_quantity": old_quant.quantity - line.rx_qty}
                    )
                    old_quant.action_apply_inventory()

                owned_quant = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", line.rx_stock_quant_id.product_id.id),
                        ("location_id", "=", line.rx_stock_quant_id.location_id.id),
                        ("owner_id", "=", self.rx_partner_id.id),
                    ],
                    limit=1,
                )

                if owned_quant:
                    owned_quant.write(
                        {"inventory_quantity": owned_quant.quantity + line.rx_qty}
                    )
                    owned_quant.action_apply_inventory()
                    line.write({"rx_stock_quant_id": owned_quant.id})

                else:
                    new_quant = self.env["stock.quant"].create(
                        {
                            "product_id": line.rx_stock_quant_id.product_id.id,
                            "location_id": line.rx_stock_quant_id.location_id.id,
                            "quantity": line.rx_qty,
                            "owner_id": self.rx_partner_id.id,
                        }
                    )

                    line.write({"rx_stock_quant_id": new_quant.id})

    def unassign_owner(self):
        for line in self.rx_task_order_line_ids:
            if not line.rx_stock_quant_id.owner_id:
                continue
            if line.rx_lot_ids:
                line.rx_stock_quant_id.write({"owner_id": False})
            else:
                no_owner_quant = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", line.rx_stock_quant_id.product_id.id),
                        ("location_id", "=", line.rx_stock_quant_id.location_id.id),
                        ("owner_id", "=", False),
                    ],
                    limit=1,
                )
                owned_quant = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", line.rx_stock_quant_id.product_id.id),
                        ("location_id", "=", line.rx_stock_quant_id.location_id.id),
                        ("owner_id", "=", self.rx_partner_id.id),
                    ],
                    limit=1,
                )
                if no_owner_quant and owned_quant:
                    no_owner_quant.write(
                        {"inventory_quantity": no_owner_quant.quantity + line.rx_qty}
                    )
                    no_owner_quant.action_apply_inventory()
                    owned_quant.write(
                        {"inventory_quantity": owned_quant.quantity - line.rx_qty}
                    )
                    owned_quant.action_apply_inventory()
                    line.write({"rx_stock_quant_id": no_owner_quant.id})

                if not no_owner_quant and owned_quant:
                    new_quant = self.env["stock.quant"].create(
                        {
                            "product_id": line.rx_stock_quant_id.product_id.id,
                            "location_id": line.rx_stock_quant_id.location_id.id,
                            "quantity": line.rx_qty,
                        }
                    )
                    new_quant.action_apply_inventory()
                    owned_quant.write(
                        {"inventory_quantity": owned_quant.quantity - line.rx_qty}
                    )
                    owned_quant.action_apply_inventory()
                    line.write({"rx_stock_quant_id": new_quant.id})

    def transfer_stock(self, line, final_location):
        picking_type_id = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.rx_warehouse_id.id),
                ("code", "=", "internal"),
            ],
            limit=1,
        )

        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.rx_provider.id,
                "picking_type_id": picking_type_id.id,
                "location_id": line.rx_location_id.id,
                "location_dest_id": final_location.id,
                "move_ids_without_package": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.rx_stock_quant_id.product_id.id,
                            "name": line.rx_stock_quant_id.product_id.name,
                            "description_picking": line.rx_stock_quant_id.product_id.name,
                            "location_id": line.rx_location_id.id,
                            "location_dest_id": final_location.id,
                            "product_uom": line.rx_stock_quant_id.product_id.uom_id.id,
                            "quantity_done": line.rx_qty - len(line.rx_lot_ids),
                            "product_uom_qty": line.rx_qty,
                            "reserved_availability": line.rx_qty,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        for move in picking.move_ids_without_package:
            move.write({"lot_ids": line.rx_lot_ids.ids})
        picking.button_validate()

    def transfer_product(self, line, origin_location, final_location):
        picking_type_id = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.rx_warehouse_id.id),
                ("code", "=", "internal"),
            ],
            limit=1,
        )

        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.rx_provider.id,
                "picking_type_id": picking_type_id.id,
                "location_id": origin_location.id,
                "location_dest_id": final_location.id,
                "move_ids_without_package": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.rx_product_id.id,
                            "name": line.rx_product_id.name,
                            "description_picking": line.rx_product_id.name,
                            "location_id": origin_location.id,
                            "location_dest_id": final_location.id,
                            "product_uom": line.rx_product_id.uom_id.id,
                            "quantity_done": line.rx_qty - len(line.rx_lot_ids),
                            "product_uom_qty": line.rx_qty,
                            "reserved_availability": line.rx_qty,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        for move in picking.move_ids_without_package:
            move.write({"lot_ids": line.rx_lot_ids.ids})
        picking.button_validate()

    def _force_change_stage(self, stage_name):
        new_stage_id = self.env["project.task.type"].search(
            [("name", "=", stage_name), ("project_ids", "in", [self.project_id.id])],
            limit=1,
        )
        self.write({"stage_id": new_stage_id.id})

    def check_all_lines_done(self):
        return all(line.rx_is_done for line in self.rx_task_order_line_ids)

    def check_available_quant(self):
        if self.rx_stock_from_other_warehouse:
            return True
        return all(
            line.rx_available_quant >= line.rx_qty
            for line in self.rx_task_order_line_ids
        )

    def check_all_lines_final_location(self):
        return all(line.rx_final_location for line in self.rx_task_order_line_ids)

    @api.depends("rx_task_order_line_ids")
    def _compute_total_count(self):
        for record in self:
            total_count = sum(record.rx_task_order_line_ids.mapped("rx_qty"))
            record.rx_total_count = total_count


class TaskOrderLine(models.Model):
    _name = "project.task.order.line"

    rx_task_id = fields.Many2one("project.task", string="Task")
    rx_warehouse_id = fields.Many2one(
        related="rx_task_id.rx_warehouse_id", readonly=True
    )
    rx_task_order_type = fields.Selection(related="rx_task_id.rx_order_type")

    rx_is_done = fields.Boolean(string="Done")

    # assets request - re-stock deposit - returns
    rx_available_stock_ids = fields.Many2many(
        "stock.quant", related="rx_task_id.rx_available_stock_ids"
    )
    rx_stock_quant_id = fields.Many2one(
        "stock.quant", string="Stock", domain="[('id', 'in', rx_available_stock_ids)]"
    )

    # assets purchase
    rx_product_id = fields.Many2one("product.product", string="Product")

    rx_available_quant = fields.Float(
        string="Available", related="rx_stock_quant_id.available_quantity"
    )
    rx_location_id = fields.Many2one(
        "stock.location", string="Location", related="rx_stock_quant_id.location_id"
    )
    rx_final_location = fields.Many2one("stock.location", string="Final location")
    rx_qty = fields.Integer("Quantity", required=True, default=1)
    rx_lot_ids = fields.Many2many("stock.production.lot", string="Lot/Serial numbers")

    @api.onchange("rx_stock_quant_id")
    def _onchange_rx_stock_quant_id(self):
        if self.rx_stock_quant_id.lot_id:
            self.rx_lot_ids = self.rx_stock_quant_id.lot_id
