-- Bornă core schema (NVDB-like). See docs/ROADMAP.md §3.
-- Geometry is stored in EPSG:4326. Lengths and chainage are computed in
-- EPSG:3844 (Stereo 70): ST_Length(ST_Transform(geom, 3844)).

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS raw;    -- untouched source imports (osm2pgsql, ogr2ogr, …)
CREATE SCHEMA IF NOT EXISTS borna;  -- the reference network and its attributes

SET search_path = borna, public;

-- Every value in Bornă traces back to a row here.
CREATE TABLE source (
    source_id     text PRIMARY KEY,               -- 'osm', 'hg540', 'cestrin_aadt_2022', …
    name          text NOT NULL,
    url           text,
    licence       text NOT NULL,                  -- 'ODbL-1.0', 'public-domain (Legea 8/1996 art. 9)', …
    attribution   text,
    retrieved_at  timestamptz NOT NULL,
    notes         text
);

-- The official register (HG 540/2000 and its amendments).
CREATE TABLE road (
    road_id           serial PRIMARY KEY,
    ref               text NOT NULL,              -- normalised: 'A1', 'DN1', 'DJ103', 'DC15B'
    category          text NOT NULL CHECK (category IN ('A', 'DX', 'DN', 'DJ', 'DC', 'street')),
    county            text,                       -- SIRUTA county code or ISO 3166-2:RO; NULL for national roads
    route_desc        text,                       -- e.g. 'Brăiești (DN 2E) – gara Lucăcești – Măzănăești (DJ 209C)'
    km_from_official  numeric(9,3),
    km_to_official    numeric(9,3),
    length_official   numeric(9,3),               -- km
    legal_source      text,                       -- the act, e.g. 'HG 540/2000 anexa 2.38, mod. HG 782/2014'
    source_id         text NOT NULL REFERENCES source,
    UNIQUE (ref, county)
);

CREATE TABLE road_segment (
    seg_id      serial PRIMARY KEY,
    road_id     integer NOT NULL REFERENCES road ON DELETE CASCADE,
    sequence    integer NOT NULL,
    km_from     numeric(9,3) NOT NULL,
    km_to       numeric(9,3) NOT NULL,
    geom        geometry(LineString, 4326) NOT NULL,
    length_m    double precision GENERATED ALWAYS AS (ST_Length(ST_Transform(geom, 3844))) STORED,
    km_quality  text NOT NULL CHECK (km_quality IN ('calibrated', 'interpolated', 'estimated')),
    source_id   text NOT NULL REFERENCES source,
    UNIQUE (road_id, sequence)
);
CREATE INDEX road_segment_geom_idx ON road_segment USING gist (geom);

-- Linear attributes along a road: source, date and licence are mandatory.
CREATE TABLE attribute_event (
    event_id     serial PRIMARY KEY,
    road_id      integer NOT NULL REFERENCES road ON DELETE CASCADE,
    km_from      numeric(9,3) NOT NULL,
    km_to        numeric(9,3) NOT NULL,
    type         text NOT NULL CHECK (type IN
                   ('surface', 'lanes', 'maxspeed', 'aadt', 'width', 'bridge', 'tunnel', 'works', 'ten_t')),
    value        text NOT NULL,
    source_id    text NOT NULL REFERENCES source,
    source_date  date NOT NULL,
    licence      text NOT NULL,
    CHECK (km_to >= km_from)
);
CREATE INDEX attribute_event_road_idx ON attribute_event (road_id, type, km_from);

-- Point objects at a km position (milestones, bridges, culverts, crossings, …).
CREATE TABLE point_object (
    obj_id       serial PRIMARY KEY,
    road_id      integer REFERENCES road ON DELETE CASCADE,
    km           numeric(9,3),
    type         text NOT NULL,
    props        jsonb NOT NULL DEFAULT '{}',
    geom         geometry(Point, 4326),
    source_id    text NOT NULL REFERENCES source,
    source_date  date NOT NULL,
    licence      text NOT NULL
);
CREATE INDEX point_object_geom_idx ON point_object USING gist (geom);
