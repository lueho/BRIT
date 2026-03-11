BEGIN;

DO $$
DECLARE
    v_user_id integer;
    v_ct_id integer;
BEGIN
    SELECT id
    INTO v_user_id
    FROM auth_user
    WHERE username = 'JBerger@UHH';

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User % not found in auth_user.username', 'JBerger@UHH';
    END IF;

    SELECT id
    INTO v_ct_id
    FROM django_content_type
    WHERE app_label = 'materials'
      AND model = 'analyticalmethod';

    IF v_ct_id IS NULL THEN
        RAISE EXCEPTION 'ContentType materials.analyticalmethod not found';
    END IF;

    DELETE FROM object_management_reviewaction
    WHERE content_type_id = v_ct_id;

    UPDATE materials_analyticalmethod
    SET owner_id = v_user_id,
        publication_status = 'private',
        submitted_at = NULL,
        approved_at = NULL,
        approved_by_id = NULL;
END
$$;

COMMIT;
