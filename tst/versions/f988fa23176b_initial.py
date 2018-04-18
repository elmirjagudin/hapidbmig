"""initial

Revision ID: f988fa23176b
Revises: 
Create Date: 2018-04-13 13:53:54.433682

"""
import json
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f988fa23176b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade_admins():
    table = "admins"

    op.alter_column(
        table,
        "name",
        type_=sa.String(128),
        existing_nullable=False,
    )

    op.create_unique_constraint(
        None,
        table,
        ["name"]
    )


def upgrade_users():
    table = "users"

    op.alter_column(
        table,
        "name",
        type_=sa.String(128),
        existing_nullable=False,
    )

    # drop 'not null' constraint
    op.alter_column(
        table,
        "note",
        type_=sa.Text,
        existing_nullable=False,
        nullable=True,
    )

    op.create_unique_constraint(
        None,
        table,
        ["name"]
    )


def upgrade_devices():
    table = "devices"

    def _fetch_id_to_name():
        id_map = {}
        con = op.get_bind()

        for (id, serno) in con.execute("select id, deviceName from devices"):
            id_map[id] = serno

        return id_map

    id_to_serno = _fetch_id_to_name()

    # rename column deviceName to serialNo
    op.alter_column(
        table,
        "deviceName",
        new_column_name="serialNo",
        type_= sa.String(16),
        existing_nullable=False,
    )

    # drop 'id' column
    op.drop_constraint("firmware_ibfk_1", "firmware", "foreignkey")
    op.drop_constraint("modelConfigs_ibfk_1", "modelConfigs", "foreignkey")

    op.drop_column(
        "devices",
        "id"
    )

    # make 'serialNo' new primary key
    op.create_primary_key(
        None, table,
        ["serialNo"]
    )

    # drop 'not null' constraint from 'note' column
    op.alter_column(
        table,
        "note",
        type_=sa.Text,
        nullable=True,
    )

    return id_to_serno


def upgrade_firmware(id_to_serno):
    table = "firmware"

    def _update_device_ids():
        # replace the device IDs with device's serial number
        # in the 'device' column
        con = op.get_bind()

        for id, serno in id_to_serno.items():
            r = con.execute(
                "update firmware set device='%s' where device = '%s';" % \
                (serno, id))

    op.alter_column(
        table,
        "deviceId",
        new_column_name="device",
        type_= sa.String(16),
        existing_nullable=False,
    )

    _update_device_ids()

    op.create_foreign_key(
        "firmware_ibfk_1",
        table,
        "devices",
        ["device"],
        ["serialNo"],
        ondelete="cascade",
    )


def upgrade_sweref_pos():
    table = "sweref_pos"

    return op.create_table(
        table,
        sa.Column("id", sa.INTEGER, primary_key=True),
        sa.Column("projection", sa.VARCHAR(8)),
        sa.Column("x", sa.DECIMAL(15,5)),
        sa.Column("y", sa.DECIMAL(15, 5)),
        sa.Column("z", sa.DECIMAL(15, 5)),
        sa.Column("roll", sa.DECIMAL(15, 5), server_default="0"),
        sa.Column("pitch", sa.DECIMAL(15, 5), server_default="0"),
        sa.Column("yaw", sa.DECIMAL(15, 5), server_default="0"),
    )


def upgrade_models():
    def _set_uploaded_to_non_zero():
        con = op.get_bind()
        r = con.execute("select id, uploaded from models")

        bad_hombres = []
        for id, uploaded in r:
            if uploaded != "0000-00-00 00:00:00":
                # this timestamp is OK
                continue

            bad_hombres.append(id)

        for id in bad_hombres:
            con.execute("update models set uploaded='1989-01-01 00:00:00' where id=%s", id)

        return bad_hombres

    def _set_uploadedOn_to_null(ids):
        con = op.get_bind()

        for id in ids:
            con.execute("update models set uploadedOn=null where id=%s" % id)

    table = "models"

    op.alter_column(
        table,
        "userID",
        new_column_name="uploader",
        type_= sa.Integer,
    )

    op.alter_column(
        table,
        "modelName",
        new_column_name="name",
        type_= sa.Text,
        nullable=True,
    )

    op.drop_column(table, "metaData")

    null_timestamp_ids = _set_uploaded_to_non_zero()

    op.alter_column(
        table,
        "uploaded",
        new_column_name="uploadedOn",
        type_= sa.DateTime,
        nullable=True,
    )

    _set_uploadedOn_to_null(null_timestamp_ids)

    op.drop_constraint("models_ibfk_1", table, "foreignkey")
    op.create_foreign_key(
        "models_ibfk_1",
        table,
        "users",
        ["uploader"],
        ["id"],
    )

    op.add_column(table,
                  sa.Column("defaultPosition",
                            sa.Integer,
                            sa.ForeignKey("sweref_pos.id")))
    op.add_column(table, sa.Column("description", sa.Text))


def upgrade_assets():
    table = "assets"

    op.alter_column(
        table,
        "model_id",
        new_column_name="model",
        type_= sa.Integer,
    )


def upgrade_rest_endpoints():
    table = "rest_endpoints"

    op.create_table(
        table,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("url", sa.Text),
        sa.Column("method", sa.Text),
    )


def upgrade_http_headers():
    table = "http_headers"

    op.create_table(
        table,
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text),
        sa.Column("restEndpoint",
                  sa.Integer,
                  sa.ForeignKey("rest_endpoints.id"),
                  primary_key=True),
    )


def upgrade_subscriptions():
    table = "subscriptions"

    op.create_table(
        table,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("expiration", sa.Integer),
        sa.Column("device", sa.String(16),
                  sa.ForeignKey("devices.serialNo", ondelete="cascade"),
                  nullable=False),
        sa.Column("restEndpoint",
                  sa.Integer,
                  sa.ForeignKey("rest_endpoints.id", ondelete="cascade")),
        # collate and charset must be set, so
        # that collation of 'device' column matches
        # collation of 'devices.serialNo' column
        mysql_COLLATE="utf8_unicode_ci",
        mysql_DEFAULT_CHARSET='utf8',
    )


def upgrade_event_topics():
    table = "event_topics"

    op.create_table(
        table,
        sa.Column("topic", sa.String(64), primary_key=True),
        sa.Column("subscription",
                  sa.Integer,
                  sa.ForeignKey("subscriptions.id"),
                  primary_key=True),
    )


#
# contains insert values for a row in 'sweref_pos' table
#
class Position:
    PROJS = {
        "sweref_99_tm": "TM",
        "sweref_99_12_00": "12 00",
        "sweref_99_13_30": "13 30",
        "sweref_99_15_00": "15 00",
        "sweref_99_16_30": "16 30",
        "sweref_99_18_00": "18 00",
        "sweref_99_14_15": "14 15",
        "sweref_99_15_45": "15 45",
        "sweref_99_17_15": "17 15",
        "sweref_99_18_45": "18 45",
        "sweref_99_20_15": "20 15",
        "sweref_99_21_45": "21 45",
        "sweref_99_23_15": "23 15",
    }

    def __init__(self, vals):
        def _filter_empty(val):
            if val == "":
                return 0.0
            return val

        self.insert_dict = dict(
            projection=Position.PROJS[vals["userProjectionRef"]],
            x=_filter_empty(vals["userLatitudeX"]),
            y=_filter_empty(vals["userLongitudeY"]),
            z=_filter_empty(vals["userAltitude"]),
            yaw=vals["userRotation"],
        )

#
# contains insert values for a row in 'model_instances' table
#
class ModelInstance:
    def __init__(self, device, model, conf):
        self.insert_dict = dict(
            device=device,
            model=model,
            hidden=conf["hide"],
            name=conf["name"],
        )

        self.pos = Position(conf)


def upgrade_model_instances(sweref_pos_table, id_to_serno):
    def _mod_conf_as_inst(con, id_to_serno):
        # convert data stored in 'modelConfigs' into
        # representation that can be stored in 'model_instances'
        # and 'swref_pos' tables
        r = con.execute("select deviceID, modelID, configuration from modelConfigs")
        for dev_id, mod_id, conf_json in r:
            conf = json.loads(conf_json)
            if conf["userProjectionRef"] == "osgb36":
                raise Exception("Can't migrate model %s on dev %s, "
                                "it's got osgb36 projection" % (mod_id, id_to_serno[dev_id]))
            yield ModelInstance(id_to_serno[dev_id], mod_id, conf)

    def _drop_invalid_model_instances(con):
        #
        # We need to remove invalid instances, that is
        # instantiated model and device have different organization ID,
        # then remove the it.
        #
        # The reason that such instances can exist, is due to old bug in
        # the cloud code, where modelConfigs row where not properly purged
        # when device's organization was changed.
        # Thus, a device would potentially still have modelConfigs for
        # models in the old organization.
        query = \
            "select mi.id, mi.position from model_instances as mi, devices, models " \
            "    where devices.serialNo = mi.device and " \
            "           models.id = mi.model and " \
            "           devices.orgID != models.orgID"

        for mid, pos_id in con.execute(query):
            con.execute("delete from model_instances where id = '%s'" % mid)
            con.execute("delete from sweref_pos where id = '%s'" % pos_id)

    # first, we make 'model_instances' table
    table = op.create_table(
        "model_instances",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("hidden", sa.Boolean, server_default="0"),
        sa.Column("model", sa.Integer, sa.ForeignKey("models.id")),
        sa.Column("position", sa.Integer, sa.ForeignKey("sweref_pos.id")),
        sa.Column("device", sa.String(16), sa.ForeignKey("devices.serialNo")),
        # collate and charset must be set, so
        # that collation of 'device' column matches
        # collation of 'devices.serialNo' column
        mysql_COLLATE="utf8_unicode_ci",
        mysql_DEFAULT_CHARSET='utf8',
    )


    # then, we convert data in 'modelConfigs' table and
    # put it in 'sweref_pos' and 'model_instances' tables
    con = op.get_bind()

    for inst in _mod_conf_as_inst(con, id_to_serno):
        pos = inst.pos
        r = con.execute(sweref_pos_table.insert(),
                        pos.insert_dict)

        inst.insert_dict["position"] = r.inserted_primary_key[0]

        con.execute(table.insert(), inst.insert_dict)


    # then, retire 'modelConfigs' table to valhalla
    op.drop_table("modelConfigs")

    # and now drop invalid model instances
    _drop_invalid_model_instances(con)


def upgrade_sessions():
    table = "sessions"

    op.create_table(
        table,
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("access", sa.Integer),
        sa.Column("data", sa.Text),
    )


def upgrade():
    upgrade_admins()
    upgrade_users()
    id_to_serial_no = upgrade_devices()
    upgrade_firmware(id_to_serial_no)
    upgrade_rest_endpoints()
    upgrade_subscriptions()
    upgrade_http_headers()
    upgrade_event_topics()
    sweref_pos_table = upgrade_sweref_pos()
    upgrade_models()
    upgrade_model_instances(sweref_pos_table, id_to_serial_no)
    upgrade_assets()
    upgrade_sessions()

    # it's not used anymore
    op.drop_table("modelSWEREFPositions")


def downgrade():
    pass
