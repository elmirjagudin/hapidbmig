"""initial

Revision ID: f988fa23176b
Revises: 
Create Date: 2018-04-13 13:53:54.433682

"""
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

    op.alter_column(
        table,
        "deviceName",
        new_column_name="serialNo",
        type_= sa.String(16),
        existing_nullable=False,
    )

    op.drop_constraint("firmware_ibfk_1", "firmware", "foreignkey")
    op.drop_constraint("modelConfigs_ibfk_1", "modelConfigs", "foreignkey")

    op.drop_column(
        "devices",
        "id"
    )

    # TODO on firmware table add foreignkey constraint on firmware.device

    op.create_primary_key(
        None, table,
        ["serialNo"]
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

    op.create_table(
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


def upgrade():
    upgrade_admins()
    upgrade_users()
    id_to_serial_no = upgrade_devices()
    upgrade_firmware(id_to_serial_no)
    upgrade_sweref_pos()
    upgrade_models()


def downgrade():
    pass
