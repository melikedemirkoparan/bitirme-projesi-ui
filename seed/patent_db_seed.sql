--
-- PostgreSQL database dump
--

\restrict 3bcnw4Mwtw93dRkgTZ12tv2e1L5ymCtjNFe0VaKDayYAc1RobIevX8sdL3foChp

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: app_setting; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_setting (
    key character varying(128) NOT NULL,
    value text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: claim; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claim (
    claim_id integer NOT NULL,
    patent_id integer NOT NULL,
    claim_number integer NOT NULL,
    claim_dependency_type character varying(20) NOT NULL,
    claim_category character varying(20) NOT NULL,
    claim_text text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    parent_claim_ids json DEFAULT '[]'::json NOT NULL
);


--
-- Name: claim_claim_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.claim_claim_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: claim_claim_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.claim_claim_id_seq OWNED BY public.claim.claim_id;


--
-- Name: claim_element; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claim_element (
    claim_element_id integer NOT NULL,
    claim_id integer NOT NULL,
    element_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    order_index integer NOT NULL
);


--
-- Name: claim_element_claim_element_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.claim_element_claim_element_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: claim_element_claim_element_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.claim_element_claim_element_id_seq OWNED BY public.claim_element.claim_element_id;


--
-- Name: element; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.element (
    element_id integer NOT NULL,
    patent_id integer NOT NULL,
    element_name character varying(255) NOT NULL,
    reference_number character varying(10) NOT NULL,
    definition_text text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: element_element_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.element_element_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: element_element_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.element_element_id_seq OWNED BY public.element.element_id;


--
-- Name: invention_disclosure; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invention_disclosure (
    idf_id integer NOT NULL,
    patent_id integer NOT NULL,
    prior_art_and_problems text,
    closest_prior_patents text,
    novel_features text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    bbf_text text
);


--
-- Name: invention_disclosure_document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invention_disclosure_document (
    document_id integer NOT NULL,
    idf_id integer NOT NULL,
    original_filename character varying(512) NOT NULL,
    stored_filename character varying(512) NOT NULL,
    mime_type character varying(255),
    size_bytes integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: invention_disclosure_document_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invention_disclosure_document_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invention_disclosure_document_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invention_disclosure_document_document_id_seq OWNED BY public.invention_disclosure_document.document_id;


--
-- Name: invention_disclosure_idf_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invention_disclosure_idf_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invention_disclosure_idf_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invention_disclosure_idf_id_seq OWNED BY public.invention_disclosure.idf_id;


--
-- Name: inventor_qa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventor_qa (
    qna_id integer NOT NULL,
    patent_id integer NOT NULL,
    questions_and_answers text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: inventor_qa_document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventor_qa_document (
    document_id integer NOT NULL,
    qna_id integer NOT NULL,
    original_filename character varying(512) NOT NULL,
    stored_filename character varying(512) NOT NULL,
    mime_type character varying(255),
    size_bytes integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: inventor_qa_document_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inventor_qa_document_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventor_qa_document_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inventor_qa_document_document_id_seq OWNED BY public.inventor_qa_document.document_id;


--
-- Name: inventor_qa_qna_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inventor_qa_qna_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventor_qa_qna_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inventor_qa_qna_id_seq OWNED BY public.inventor_qa.qna_id;


--
-- Name: patent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patent (
    patent_id integer NOT NULL,
    patent_name character varying(255) NOT NULL,
    patent_owner character varying(255) NOT NULL,
    patent_draft text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    domain character varying(255),
    invention_context text
);


--
-- Name: patent_patent_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patent_patent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patent_patent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patent_patent_id_seq OWNED BY public.patent.patent_id;


--
-- Name: research_report; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_report (
    research_report_id integer NOT NULL,
    patent_id integer NOT NULL,
    executive_summary text,
    search_strategy text,
    classification_and_keywords text,
    element_patent_analysis text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: research_report_document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_report_document (
    document_id integer NOT NULL,
    research_report_id integer NOT NULL,
    original_filename character varying(512) NOT NULL,
    stored_filename character varying(512) NOT NULL,
    mime_type character varying(255),
    size_bytes integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: research_report_document_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.research_report_document_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: research_report_document_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.research_report_document_document_id_seq OWNED BY public.research_report_document.document_id;


--
-- Name: research_report_research_report_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.research_report_research_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: research_report_research_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.research_report_research_report_id_seq OWNED BY public.research_report.research_report_id;


--
-- Name: claim claim_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim ALTER COLUMN claim_id SET DEFAULT nextval('public.claim_claim_id_seq'::regclass);


--
-- Name: claim_element claim_element_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_element ALTER COLUMN claim_element_id SET DEFAULT nextval('public.claim_element_claim_element_id_seq'::regclass);


--
-- Name: element element_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.element ALTER COLUMN element_id SET DEFAULT nextval('public.element_element_id_seq'::regclass);


--
-- Name: invention_disclosure idf_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure ALTER COLUMN idf_id SET DEFAULT nextval('public.invention_disclosure_idf_id_seq'::regclass);


--
-- Name: invention_disclosure_document document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure_document ALTER COLUMN document_id SET DEFAULT nextval('public.invention_disclosure_document_document_id_seq'::regclass);


--
-- Name: inventor_qa qna_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa ALTER COLUMN qna_id SET DEFAULT nextval('public.inventor_qa_qna_id_seq'::regclass);


--
-- Name: inventor_qa_document document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa_document ALTER COLUMN document_id SET DEFAULT nextval('public.inventor_qa_document_document_id_seq'::regclass);


--
-- Name: patent patent_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patent ALTER COLUMN patent_id SET DEFAULT nextval('public.patent_patent_id_seq'::regclass);


--
-- Name: research_report research_report_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report ALTER COLUMN research_report_id SET DEFAULT nextval('public.research_report_research_report_id_seq'::regclass);


--
-- Name: research_report_document document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report_document ALTER COLUMN document_id SET DEFAULT nextval('public.research_report_document_document_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.alembic_version VALUES ('23fbf1ca0df3');


--
-- Data for Name: claim; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.claim VALUES (9, 9, 1, 'independent', 'apparatus', NULL, '2026-05-27 08:10:32.697811', '2026-05-27 08:10:32.697811', '[]');
INSERT INTO public.claim VALUES (11, 10, 2, 'dependent', 'apparatus', 'Catadioptric Multi FoV and Multi Wavelength Optical System according to claim 1, further comprising an Image group (D), forming an intermediate image plane.', '2026-06-03 13:36:54.948209', '2026-06-03 13:38:29.073474', '[10]');
INSERT INTO public.claim VALUES (13, 13, 2, 'dependent', 'apparatus', 'Clamp Holder for Actuator Hydraulics according to claim 1, further comprising an Actuator (4), moving the fluid within the transmission line.', '2026-06-03 13:52:11.945686', '2026-06-03 13:52:24.299647', '[12]');
INSERT INTO public.claim VALUES (10, 10, 1, 'independent', 'apparatus', 'Catadioptric Multi FoV and Multi Wavelength Optical System comprising a Catadioptric lens system (S), providing very long focal lengths while remaining physically compact; characterized in that the Catadioptric Multi FoV and Multi Wavelength Optical System further comprises a Primary mirror (1), forming the intermediate image plane.', '2026-06-03 13:32:59.73573', '2026-06-03 17:23:16.115368', '[]');
INSERT INTO public.claim VALUES (12, 13, 1, 'independent', 'apparatus', 'Clamp Holder for Actuator Hydraulics characterized in that it comprises a Body (2), positioned within the rudder direction, a Transmission line (3), generating mechanical force from contained fluid.', '2026-06-03 13:52:02.372746', '2026-06-03 17:29:44.611872', '[]');


--
-- Data for Name: claim_element; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.claim_element VALUES (32, 9, 142, '2026-05-27 08:10:38.455425', '2026-05-27 08:10:38.455425', 1);
INSERT INTO public.claim_element VALUES (33, 9, 143, '2026-05-27 08:10:38.592322', '2026-05-27 08:10:38.592322', 2);
INSERT INTO public.claim_element VALUES (34, 9, 144, '2026-05-27 08:10:38.706993', '2026-05-27 08:10:38.706993', 3);
INSERT INTO public.claim_element VALUES (35, 10, 167, '2026-06-03 13:34:05.455366', '2026-06-03 13:34:05.455366', 1);
INSERT INTO public.claim_element VALUES (36, 11, 170, '2026-06-03 13:37:03.15721', '2026-06-03 13:37:03.15721', 1);
INSERT INTO public.claim_element VALUES (37, 10, 174, '2026-06-03 13:37:36.957012', '2026-06-03 13:37:36.957012', 2);
INSERT INTO public.claim_element VALUES (38, 12, 208, '2026-06-03 13:52:04.084128', '2026-06-03 13:52:04.084128', 1);
INSERT INTO public.claim_element VALUES (39, 12, 209, '2026-06-03 13:52:06.168061', '2026-06-03 13:52:06.168061', 2);
INSERT INTO public.claim_element VALUES (40, 13, 210, '2026-06-03 13:52:13.673229', '2026-06-03 13:52:13.673229', 1);


--
-- Data for Name: element; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.element VALUES (225, 13, 'Fastener - on extension', '7', NULL, '2026-05-24 15:45:21.446208', '2026-05-24 15:45:21.446208');
INSERT INTO public.element VALUES (166, 9, 'Body - mirror symmetric', '2', NULL, '2026-05-24 13:08:34.953072', '2026-05-24 13:08:34.953072');
INSERT INTO public.element VALUES (226, 13, 'Bearing element - flexible', '8', NULL, '2026-05-24 15:45:21.481486', '2026-05-24 15:45:21.481486');
INSERT INTO public.element VALUES (227, 13, 'Body - rudder', '2', NULL, '2026-05-24 15:45:21.598696', '2026-05-24 15:45:21.598696');
INSERT INTO public.element VALUES (141, 9, 'Munition', 'M', NULL, '2026-05-24 13:08:34.17639', '2026-05-24 13:08:34.17639');
INSERT INTO public.element VALUES (145, 9, 'Shoe rod', '5', NULL, '2026-05-24 13:08:34.343103', '2026-05-24 13:08:34.343103');
INSERT INTO public.element VALUES (146, 9, 'Transmission rod', '6', NULL, '2026-05-24 13:08:34.373286', '2026-05-24 13:08:34.373286');
INSERT INTO public.element VALUES (147, 9, 'Center line', 'BL', NULL, '2026-05-24 13:08:34.407948', '2026-05-24 13:08:34.407948');
INSERT INTO public.element VALUES (148, 9, 'Symmetry plane', 'S', NULL, '2026-05-24 13:08:34.442238', '2026-05-24 13:08:34.442238');
INSERT INTO public.element VALUES (149, 9, 'Vertical plane', 'S''', NULL, '2026-05-24 13:08:34.469373', '2026-05-24 13:08:34.469373');
INSERT INTO public.element VALUES (150, 9, 'Shoe rod - movable in vertical plane', '5', NULL, '2026-05-24 13:08:34.49625', '2026-05-24 13:08:34.49625');
INSERT INTO public.element VALUES (151, 9, 'Adjustment tool', 'A', NULL, '2026-05-24 13:08:34.525603', '2026-05-24 13:08:34.525603');
INSERT INTO public.element VALUES (152, 9, 'Adjustment opening', '7', NULL, '2026-05-24 13:08:34.557571', '2026-05-24 13:08:34.557571');
INSERT INTO public.element VALUES (153, 9, 'Motion transmission shaft', '8', NULL, '2026-05-24 13:08:34.583011', '2026-05-24 13:08:34.583011');
INSERT INTO public.element VALUES (154, 9, 'Motion transmission shaft - rectangular profile', '8', NULL, '2026-05-24 13:08:34.611054', '2026-05-24 13:08:34.611054');
INSERT INTO public.element VALUES (155, 9, 'Locker', '9', NULL, '2026-05-24 13:08:34.639288', '2026-05-24 13:08:34.639288');
INSERT INTO public.element VALUES (156, 9, 'Adjustment opening - on both sides', '7', NULL, '2026-05-24 13:08:34.665921', '2026-05-24 13:08:34.665921');
INSERT INTO public.element VALUES (157, 9, 'Stopper', '10', NULL, '2026-05-24 13:08:34.692895', '2026-05-24 13:08:34.692895');
INSERT INTO public.element VALUES (158, 9, 'Threaded portion', '11', NULL, '2026-05-24 13:08:34.718072', '2026-05-24 13:08:34.718072');
INSERT INTO public.element VALUES (159, 9, 'Fastener', '12', NULL, '2026-05-24 13:08:34.744238', '2026-05-24 13:08:34.744238');
INSERT INTO public.element VALUES (160, 9, 'Flanged bushing', '13', NULL, '2026-05-24 13:08:34.777386', '2026-05-24 13:08:34.777386');
INSERT INTO public.element VALUES (161, 9, 'Sensor', '14', NULL, '2026-05-24 13:08:34.803182', '2026-05-24 13:08:34.803182');
INSERT INTO public.element VALUES (162, 9, 'Motor', '15', NULL, '2026-05-24 13:08:34.832978', '2026-05-24 13:08:34.832978');
INSERT INTO public.element VALUES (163, 9, 'Control unit', '16', NULL, '2026-05-24 13:08:34.859089', '2026-05-24 13:08:34.859089');
INSERT INTO public.element VALUES (164, 9, 'Rotating rod - two separate parts', '4', NULL, '2026-05-24 13:08:34.885524', '2026-05-24 13:08:34.885524');
INSERT INTO public.element VALUES (165, 9, 'Shoe - perpendicular support', '3', NULL, '2026-05-24 13:08:34.911268', '2026-05-24 13:08:34.911268');
INSERT INTO public.element VALUES (168, 10, 'Secondary mirror', '2', NULL, '2026-05-24 13:41:25.122203', '2026-05-24 13:41:25.122203');
INSERT INTO public.element VALUES (169, 10, 'Objective lens group', 'G', NULL, '2026-05-24 13:41:25.150752', '2026-05-24 13:41:25.150752');
INSERT INTO public.element VALUES (171, 10, 'Movable lens group', 'H', NULL, '2026-05-24 13:41:25.204665', '2026-05-24 13:41:25.204665');
INSERT INTO public.element VALUES (172, 10, 'Intermediate image plane', '3', NULL, '2026-05-24 13:41:25.229054', '2026-05-24 13:41:25.229054');
INSERT INTO public.element VALUES (173, 10, 'Beam splitter part', '4', NULL, '2026-05-24 13:41:25.254969', '2026-05-24 13:41:25.254969');
INSERT INTO public.element VALUES (175, 10, 'First movable lens group', 'H1', NULL, '2026-05-24 13:41:25.306068', '2026-05-24 13:41:25.306068');
INSERT INTO public.element VALUES (176, 10, 'Second movable lens group', 'H2', NULL, '2026-05-24 13:41:25.334902', '2026-05-24 13:41:25.334902');
INSERT INTO public.element VALUES (177, 10, 'Beam splitter part - beam splitter cube', '4', NULL, '2026-05-24 13:41:25.360273', '2026-05-24 13:41:25.360273');
INSERT INTO public.element VALUES (178, 10, 'Beam splitter part - filter', '4', NULL, '2026-05-24 13:41:25.386154', '2026-05-24 13:41:25.386154');
INSERT INTO public.element VALUES (179, 14, 'Main housing', '2', NULL, '2026-05-24 14:20:41.315608', '2026-05-24 14:20:41.315608');
INSERT INTO public.element VALUES (180, 14, 'Main shaft', 'A', NULL, '2026-05-24 14:20:41.409417', '2026-05-24 14:20:41.409417');
INSERT INTO public.element VALUES (181, 14, 'First housing', '201', NULL, '2026-05-24 14:20:41.454925', '2026-05-24 14:20:41.454925');
INSERT INTO public.element VALUES (182, 14, 'Transmission group', 'T', NULL, '2026-05-24 14:20:41.486132', '2026-05-24 14:20:41.486132');
INSERT INTO public.element VALUES (183, 14, 'Second housing', '202', NULL, '2026-05-24 14:20:41.515547', '2026-05-24 14:20:41.515547');
INSERT INTO public.element VALUES (184, 14, 'Floor', 'Z', NULL, '2026-05-24 14:20:41.544966', '2026-05-24 14:20:41.544966');
INSERT INTO public.element VALUES (185, 14, 'Pump', '3', NULL, '2026-05-24 14:20:41.571597', '2026-05-24 14:20:41.571597');
INSERT INTO public.element VALUES (186, 14, 'Reservoir', '4', NULL, '2026-05-24 14:20:41.602501', '2026-05-24 14:20:41.602501');
INSERT INTO public.element VALUES (187, 14, 'Flange', '5', NULL, '2026-05-24 14:20:41.630406', '2026-05-24 14:20:41.630406');
INSERT INTO public.element VALUES (188, 14, 'Gear', '6', NULL, '2026-05-24 14:20:41.665415', '2026-05-24 14:20:41.665415');
INSERT INTO public.element VALUES (189, 14, 'Cavity', '7', NULL, '2026-05-24 14:20:41.692063', '2026-05-24 14:20:41.692063');
INSERT INTO public.element VALUES (190, 14, 'Fin', '8', NULL, '2026-05-24 14:20:41.720883', '2026-05-24 14:20:41.720883');
INSERT INTO public.element VALUES (191, 14, 'Opening', '9', NULL, '2026-05-24 14:20:41.752625', '2026-05-24 14:20:41.752625');
INSERT INTO public.element VALUES (192, 14, 'Flange - inclined', '5', NULL, '2026-05-24 14:20:41.78017', '2026-05-24 14:20:41.78017');
INSERT INTO public.element VALUES (193, 14, 'Window', '501', NULL, '2026-05-24 14:20:41.808803', '2026-05-24 14:20:41.808803');
INSERT INTO public.element VALUES (194, 14, 'Locknut', '10', NULL, '2026-05-24 14:20:41.834731', '2026-05-24 14:20:41.834731');
INSERT INTO public.element VALUES (195, 14, 'Extension', '801', NULL, '2026-05-24 14:20:41.861827', '2026-05-24 14:20:41.861827');
INSERT INTO public.element VALUES (196, 14, 'Extension - flat plate', '801', NULL, '2026-05-24 14:20:41.887771', '2026-05-24 14:20:41.887771');
INSERT INTO public.element VALUES (197, 14, 'Extension - concave/convex', '801', NULL, '2026-05-24 14:20:41.912789', '2026-05-24 14:20:41.912789');
INSERT INTO public.element VALUES (198, 14, 'Extension - bucket structure', '801', NULL, '2026-05-24 14:20:41.940108', '2026-05-24 14:20:41.940108');
INSERT INTO public.element VALUES (199, 14, 'Extension - radial angular intervals', '801', NULL, '2026-05-24 14:20:41.96801', '2026-05-24 14:20:41.96801');
INSERT INTO public.element VALUES (200, 14, 'Channel', '601', NULL, '2026-05-24 14:20:41.9941', '2026-05-24 14:20:41.9941');
INSERT INTO public.element VALUES (201, 14, 'Channel opening', '602', NULL, '2026-05-24 14:20:42.023173', '2026-05-24 14:20:42.023173');
INSERT INTO public.element VALUES (202, 14, 'Locknut and/or gear (6) - integral', '10', NULL, '2026-05-24 14:20:42.048954', '2026-05-24 14:20:42.048954');
INSERT INTO public.element VALUES (203, 14, 'Locknut and/or gear (6) - removable', '10', NULL, '2026-05-24 14:20:42.076302', '2026-05-24 14:20:42.076302');
INSERT INTO public.element VALUES (204, 14, 'Flange - inclined toward pump', '5', NULL, '2026-05-24 14:20:42.108714', '2026-05-24 14:20:42.108714');
INSERT INTO public.element VALUES (205, 14, 'Sensor', '11', NULL, '2026-05-24 14:20:42.131967', '2026-05-24 14:20:42.131967');
INSERT INTO public.element VALUES (206, 14, 'Cavity - conical', '7', NULL, '2026-05-24 14:20:42.161195', '2026-05-24 14:20:42.161195');
INSERT INTO public.element VALUES (207, 14, 'Reservoir - oil collecting', '4', NULL, '2026-05-24 14:20:42.188002', '2026-05-24 14:20:42.188002');
INSERT INTO public.element VALUES (211, 13, 'First holder', '5', NULL, '2026-05-24 15:45:19.353883', '2026-05-24 15:45:19.353883');
INSERT INTO public.element VALUES (212, 13, 'Second holder', '6', NULL, '2026-05-24 15:45:19.384873', '2026-05-24 15:45:19.384873');
INSERT INTO public.element VALUES (213, 13, 'Fastener', '7', NULL, '2026-05-24 15:45:19.461927', '2026-05-24 15:45:19.461927');
INSERT INTO public.element VALUES (214, 13, 'Bearing element', '8', NULL, '2026-05-24 15:45:19.504906', '2026-05-24 15:45:19.504906');
INSERT INTO public.element VALUES (215, 13, 'Flange', '9', NULL, '2026-05-24 15:45:19.601912', '2026-05-24 15:45:19.601912');
INSERT INTO public.element VALUES (216, 13, 'Extension', '10', NULL, '2026-05-24 15:45:19.69215', '2026-05-24 15:45:19.69215');
INSERT INTO public.element VALUES (217, 13, 'Flange - parallel to line', '9', NULL, '2026-05-24 15:45:19.787849', '2026-05-24 15:45:19.787849');
INSERT INTO public.element VALUES (218, 13, 'Extension - perpendicular to line', '10', NULL, '2026-05-24 15:45:20.333533', '2026-05-24 15:45:20.333533');
INSERT INTO public.element VALUES (219, 13, 'Extension - actuator-mounted', '10', NULL, '2026-05-24 15:45:20.845341', '2026-05-24 15:45:20.845341');
INSERT INTO public.element VALUES (220, 13, 'Flange - facing transmission line', '9', NULL, '2026-05-24 15:45:20.873877', '2026-05-24 15:45:20.873877');
INSERT INTO public.element VALUES (221, 13, 'Transmission line - load-carrying', '3', NULL, '2026-05-24 15:45:20.914317', '2026-05-24 15:45:20.914317');
INSERT INTO public.element VALUES (222, 13, 'Latch', '11', NULL, '2026-05-24 15:45:20.998552', '2026-05-24 15:45:20.998552');
INSERT INTO public.element VALUES (223, 13, 'Transmission line - near the flange', '3', NULL, '2026-05-24 15:45:21.029271', '2026-05-24 15:45:21.029271');
INSERT INTO public.element VALUES (224, 13, 'Transmission line - hydraulic', '3', NULL, '2026-05-24 15:45:21.103972', '2026-05-24 15:45:21.103972');
INSERT INTO public.element VALUES (239, 12, 'Body', 'G', NULL, '2026-05-26 14:22:29.903928', '2026-05-26 14:22:29.903928');
INSERT INTO public.element VALUES (240, 12, 'Intermediate part', '2', NULL, '2026-05-26 14:22:30.502181', '2026-05-26 14:22:30.502181');
INSERT INTO public.element VALUES (241, 12, 'Pipe', '3', NULL, '2026-05-26 14:22:31.138683', '2026-05-26 14:22:31.138683');
INSERT INTO public.element VALUES (242, 12, 'Equipment', 'E', NULL, '2026-05-26 14:22:31.320581', '2026-05-26 14:22:31.320581');
INSERT INTO public.element VALUES (243, 12, 'First fastener', '4', NULL, '2026-05-26 14:22:31.634697', '2026-05-26 14:22:31.634697');
INSERT INTO public.element VALUES (244, 12, 'Protrusion', '2a', NULL, '2026-05-26 14:22:31.952046', '2026-05-26 14:22:31.952046');
INSERT INTO public.element VALUES (245, 12, 'First adjustment region', '5', NULL, '2026-05-26 14:22:32.164049', '2026-05-26 14:22:32.164049');
INSERT INTO public.element VALUES (246, 12, 'Center line', 'M', NULL, '2026-05-26 14:22:32.586103', '2026-05-26 14:22:32.586103');
INSERT INTO public.element VALUES (247, 12, 'Symmetry plane', 'BL', NULL, '2026-05-26 14:22:32.798653', '2026-05-26 14:22:32.798653');
INSERT INTO public.element VALUES (248, 12, 'First adjustment axis', '3a', NULL, '2026-05-26 14:22:32.928479', '2026-05-26 14:22:32.928479');
INSERT INTO public.element VALUES (249, 12, 'Symmetric plane angle (θ)', '6', NULL, '2026-05-26 14:22:33.367957', '2026-05-26 14:22:33.367957');
INSERT INTO public.element VALUES (250, 12, 'Protrusion - symmetric plane angle', '2a', NULL, '2026-05-26 14:22:33.629264', '2026-05-26 14:22:33.629264');
INSERT INTO public.element VALUES (251, 12, 'Body plane', 'FL', NULL, '2026-05-26 14:22:34.083838', '2026-05-26 14:22:34.083838');
INSERT INTO public.element VALUES (252, 12, 'Longitudinal position angle (β)', '7', NULL, '2026-05-26 14:22:34.257073', '2026-05-26 14:22:34.257073');
INSERT INTO public.element VALUES (253, 12, 'Protrusion - longitudinal position angle', '2a', NULL, '2026-05-26 14:22:34.43635', '2026-05-26 14:22:34.43635');
INSERT INTO public.element VALUES (254, 12, 'Adapter', '6', NULL, '2026-05-26 14:22:34.724696', '2026-05-26 14:22:34.724696');
INSERT INTO public.element VALUES (255, 12, 'Second adjustment axis', '3b', NULL, '2026-05-26 14:22:34.961541', '2026-05-26 14:22:34.961541');
INSERT INTO public.element VALUES (144, 9, 'Rotating rod', '4', 'a rotating rod (4), rotatable about its axis to move the shoe into position.', '2026-05-24 13:08:34.316045', '2026-05-27 08:15:16.52449');
INSERT INTO public.element VALUES (170, 10, 'Image group', 'D', 'an Image group (D), forming an intermediate image plane', '2026-05-24 13:41:25.176973', '2026-06-03 13:37:32.307815');
INSERT INTO public.element VALUES (208, 13, 'Body', '2', 'a Body (2), positioned within the rudder direction', '2026-05-24 15:45:18.094779', '2026-06-03 13:49:23.929902');
INSERT INTO public.element VALUES (210, 13, 'Actuator', '4', 'an Actuator (4), moving the fluid within the transmission line', '2026-05-24 15:45:19.269042', '2026-06-03 13:51:59.080518');
INSERT INTO public.element VALUES (256, 12, 'Equipment fastener', '7', NULL, '2026-05-26 14:22:35.248211', '2026-05-26 14:22:35.248211');
INSERT INTO public.element VALUES (258, 12, 'Second adjustment region', '9', NULL, '2026-05-26 14:22:35.337456', '2026-05-26 14:22:35.337456');
INSERT INTO public.element VALUES (260, 12, 'Second adjustment region - circumferential', '9', NULL, '2026-05-26 14:22:35.4315', '2026-05-26 14:22:35.4315');
INSERT INTO public.element VALUES (262, 12, 'Intermediate part - fairing', '2', NULL, '2026-05-26 14:22:35.526391', '2026-05-26 14:22:35.526391');
INSERT INTO public.element VALUES (264, 12, 'Equipment - HADS', 'E', NULL, '2026-05-26 14:22:35.601996', '2026-05-26 14:22:35.601996');
INSERT INTO public.element VALUES (266, 12, 'Support element', '11', NULL, '2026-05-26 14:22:35.682731', '2026-05-26 14:22:35.682731');
INSERT INTO public.element VALUES (268, 12, 'Laser', '13', NULL, '2026-05-26 14:22:35.770933', '2026-05-26 14:22:35.770933');
INSERT INTO public.element VALUES (270, 12, 'Intermediate part - NC manufactured', '2', NULL, '2026-05-26 14:22:35.845619', '2026-05-26 14:22:35.845619');
INSERT INTO public.element VALUES (257, 12, 'Second fastener', '8', NULL, '2026-05-26 14:22:35.306192', '2026-05-26 14:22:35.306192');
INSERT INTO public.element VALUES (259, 12, 'Bearing', '10', NULL, '2026-05-26 14:22:35.385918', '2026-05-26 14:22:35.385918');
INSERT INTO public.element VALUES (261, 12, 'Stop surface', '2b', NULL, '2026-05-26 14:22:35.480943', '2026-05-26 14:22:35.480943');
INSERT INTO public.element VALUES (263, 12, 'Protrusion - three-stage adjustment', '2a', NULL, '2026-05-26 14:22:35.56361', '2026-05-26 14:22:35.56361');
INSERT INTO public.element VALUES (265, 12, 'Pipe - circular/teardrop', '3', NULL, '2026-05-26 14:22:35.643938', '2026-05-26 14:22:35.643938');
INSERT INTO public.element VALUES (267, 12, 'Mechanical clamp', '12', NULL, '2026-05-26 14:22:35.724132', '2026-05-26 14:22:35.724132');
INSERT INTO public.element VALUES (269, 12, 'Body - helicopter/UAV/aircraft', 'G', NULL, '2026-05-26 14:22:35.806762', '2026-05-26 14:22:35.806762');
INSERT INTO public.element VALUES (142, 9, 'Body', '2', 'a body (2), a structural component on the air vehicle supporting the four-bar mechanism.', '2026-05-24 13:08:34.251386', '2026-05-27 08:15:16.173781');
INSERT INTO public.element VALUES (143, 9, 'Shoe', '3', 'a shoe (3), engaging the munition for support contact.', '2026-05-24 13:08:34.284649', '2026-05-27 08:15:16.371957');
INSERT INTO public.element VALUES (167, 10, 'Primary mirror', '1', 'a Primary mirror (1), forming the intermediate image plane', '2026-05-24 13:41:25.081187', '2026-06-03 13:35:12.325278');
INSERT INTO public.element VALUES (174, 10, 'Catadioptric lens system', 'S', 'a Catadioptric lens system (S), providing very long focal lengths while remaining physically compact', '2026-05-24 13:41:25.282109', '2026-06-03 13:38:00.584471');
INSERT INTO public.element VALUES (209, 13, 'Transmission line', '3', 'a Transmission line (3), generating mechanical force from contained fluid', '2026-05-24 15:45:19.068095', '2026-06-03 13:50:08.209635');


--
-- Data for Name: invention_disclosure; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.invention_disclosure VALUES (12, 14, 'As seen in the figure on page 66 of the attached AgustaWestland document belonging to the A129 ATAK helicopter power transmission system (and below), in power transmission systems there exist cylindrical "cluster casing (1)" designs that carry the gear and bearing assembly. In the figure below, the ball bearings (3) and roller bearings (4) are first installed into the cluster casing. The gear (5) is then brought in from above, fitted onto the bearings, and the yellow-colored lock nut part (6) is tightened from the opposite side. In this way, the gear is fixed in position. The lubrication pump (7), which is brought in from below and passed through the center of the cluster casing, is driven from the spline teeth inside this lock nut (or by another mechanical connection method). For this purpose, the lubrication pump has a suitable input shaft design. The lubrication pump is also fixed to the cluster casing with bolts or studs. This assembly group is brought in from below and connected to the main housing with studs or bolts. Because the space allocated for the transmission within the aircraft is limited, a compact design is required. As seen in the figure below, the slip-fit flange section (1a) that provides the cluster casing–main housing connection has been moved upward in the vertical direction, thereby reducing the volume used by the transmission in the vertical direction. However, the disadvantage created by this application is that the base of the cluster casing is angled (1b) and oil accumulates in the resulting conical volume. Oil flowing from the lubricated gear mesh point and from the bearings accumulates at the base of the cluster casing (1b). Normally, oil flow is expected to go directly to the sump by gravity without accumulating in any region. The oil reaching the sump must pass through the chip detector and then be pressurized. However, in this design, this accumulated oil is both carried in the aircraft as extra weight, and—because it does not enter the chip detector—it carries the potential to accumulate chips. Chips accumulated in the oil reaching the rotating transmission elements as a result of a maneuver could have a catastrophic effect.', NULL, 'Element 1 — A bucket structure (8) connected to the lock nut (6) or to the bottom point of the gear (5) is used. One or more buckets rotating together with the gear help drain the oil accumulating at the base by means of a vortex effect. Thanks to the openings (9) in the cluster casing, the circulating oil is flung outward and then passes through a window-shaped opening (10), directing it toward the sump (11).
Element 2 — As an alternative to the bucket structure that flings the oil outward by the vortex (centrifugal) effect, one or more flat plates (12) can be used. In addition, for the same flow-directing purpose, more streamlined concave or convex vanes (13) can be used. The vanes (12, 13) can be connected to the gear individually, or they can be placed on a common ring and connected to the gear as a single unit.
Element 3 — The openings (9) in the cluster casing can be designed as flow-directing channels (14). In this way, the channel walls both serve as a structural element carrying the bearings above them and ensure that the flow is directed outward and reaches the sump (11) by passing through the window (10).
', '2026-05-24 11:35:00.030385', '2026-05-24 13:01:21.889461', '');
INSERT INTO public.invention_disclosure VALUES (7, 9, 'Thanks to the four-bar mechanism, the mechanism has been simplified, the number of parts has been reduced, and the weight has been decreased.

-BRU-46, BRU-47, BRU-76 have implemented the automatic sway brace system using a wedge mechanism.', 'US3670620
GB594609
US3242808
GB1529087
FR7431180
US4050656A
', 'Element 1 – Holding the Sway Brace Shaft with the Mechanical Clamp

Element 2 – Movement of the Sway Brace Shoes in a Single Plane', '2026-05-23 16:46:03.097479', '2026-05-23 16:46:52.373465', NULL);
INSERT INTO public.invention_disclosure VALUES (8, 10, 'The patent numbered US5940222 has been taken as the starting point. However, because in this and similar patents there is not more than one wavelength, the design of an optical system has been planned that—in an optical system that performs visible, near-infrared (NIR), mid-infrared (MWIR), and long-infrared (LWIR) detection, which will enable us to see every target in every weather condition—has the ability to view targets clearly and at different angles for environmental awareness.
It incorporates some of the similar features of the CATS system made by ASELSAN; however, in the invention we have made, there are design details, calculations, differences in field of view, and finally a difference in wavelength. The greatest advantage of it being LWIR is that, in order to enable establishing air-to-air superiority, it provides the situational awareness that the other wavelengths cannot provide, with longer range values.
', 'US5940222 US4714307 US4523816 US4235508 US4240702', 'Element 1 — Multiple wavelengths
Element 2 — Multiple zoom settings
Element 3 — The shortening of the optical path is achieved by the mirrors forming an intermediate image plane through mathematical calculations.
', '2026-05-23 16:57:35.802129', '2026-05-23 16:58:10.255834', NULL);
INSERT INTO public.invention_disclosure VALUES (10, 12, 'In aircraft, in the case of equipment found in the exterior regions whose placement must be carried out precisely, there can be situations where the required precision cannot be achieved through manufacturing tolerances. In such cases, the need to make an adjustment arises after equipment installation. For this reason, the equipment placement design must be carried out in a manner suitable for this.
Within the scope of the Bahrain Cobra Modernization (BCM) Project, the placement requirements of the Helicopter Air Data System (HADS) equipment are such that the installation must be at a precision of ±0.5 degrees in the pitch, roll, and yaw angles. Achieving these values through manufacturing tolerances both makes the processes complex and increases the manufacturing cost. For this reason, the necessity of making an adjustment after equipment installation arises.
In this solution for which a patent is sought, a design of 2 pipes that have different axes of rotation and fit one inside the other has been made for equipment installation. By means of the slots located on these two pipes, the angles can be changed by rotating these pipes.
With Adjustment Zone 1, the possibility of making adjustments in the roll and yaw angles is provided. With Adjustment Zone 2, the possibility of making an adjustment in the pitch angle is provided. With these adjustment capabilities, the precise angle requirements found in the equipment requirements can be met.
', NULL, 'Element 1 — For equipment with precise placement requirements, a solution that allows adjustment during installation has been offered instead of narrow manufacturing tolerances. In this way, by avoiding complex manufacturing processes, a reduction in manufacturing costs is achieved.
Element 2 — Such designs found on other helicopters in the inventory offer the possibility of adjustment in one or two angles. However, with this solution, adjustment can be made in all of the pitch, roll, and yaw angles.
', '2026-05-24 11:23:59.249731', '2026-05-24 11:27:24.734863', NULL);
INSERT INTO public.invention_disclosure VALUES (11, 13, 'Many of the Flight Control System (FCS) equipment items require a hydraulic supply. For this reason, standard clamps are used so that the hydraulic lines can be held on the actuator.
Hydraulic holder clamps occupy volume in the region, cause cost increases in procurement processes, and cause delays of the planned time in assembly processes.
As the hydraulic lines move away from the actuator, they occupy more volume in the region and increase the area swept by the mechanism. For this reason, they lead to the design of heavier structural parts.
In hydraulic clamps, the pipes are held with two separate clamps. The use of traditional clamp designs in narrow areas that are difficult to access causes incorrect routing due to tolerance accumulation.
', NULL, 'Element 1 — Unlike the traditional method, multiple hydraulic pipes located on the actuator will be able to be held with a single clamp. In this way, routing errors that could arise from tolerance accumulation will be prevented.
Element 2 — Because there is elastomeric material in the clamp-holder part, corrosion, wear, heat, and electrical conduction that could occur will be prevented.
Element 3 — The routing will be able to come as close as possible to the equipment. Because it will occupy less volume, the access problem will be eliminated.
Element 4 — The clamp-holder design can be assembled by sliding. In this way, the disassembly/assembly operation will be able to be performed from a single direction by a single person.
', '2026-05-24 11:29:58.648369', '2026-06-03 11:08:29.551332', '');


--
-- Data for Name: invention_disclosure_document; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: inventor_qa; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.inventor_qa VALUES (7, 9, '1.	Question  1: The reason the hexagonal shaft (1) is designed with the opening (2) is so that the operator can actuate both sides from a single point, isn''t it? Does the profile of part number 1 have a specific name, and can we say that the reason we make this shape is to ensure minimum stress on part number 1 during rotation? Also, if the adjustment shaft (4) is inserted into the clamp (3) from both sides, is an intermediate piece like the hexagonal shaft (1) again needed to transfer the rotation to both sides? In the case where only separate adjustment of both sides is desired, there is no need for an intermediate piece like the hexagonal shaft (1), right?3.	Answer 1:  The reason the part indicated by arrow number 2 is not made integral with the part indicated by arrow number 1 is that the shaft cannot be inserted there during production. It was designed as two separate pieces for assembly. The profile has no specific name; it generates torque from 3 surfaces and the other surface ensures correct assembly. The parts shown as numbers 1 and 4 are actually a single piece, so I could not fully understand the other questions in this item.1.	Question 2 : Why was a "castle nut and cotter pin" structure used in the connectors (9) between the connecting rods (4, 5, 6) instead of a classic bolt-nut connection? Is the purpose to prevent the nut from rotating and the connection from weakening over time? Is a problem such as weakening over time expected in the connections between the connecting rods due to the nature of the swaybrace structure? Answer 2:Yes, these are the standard bolts and nuts we use. The cotter pin is indispensable in our parts, because it prevents the nut from coming off in the event of vibration. If not used, it can cause loss of the system or, in a worse scenario, loss of the aircraft. Since vibration is a major problem inside the aircraft, we use this not just for the swaybrace, but for nearly all aircraft connections in this manner.Question  3: Is the shoe (P) moved back and forth on the shoe rod (6) by rotating the screw part (12) with a tool such as a screwdriver, thereby changing the amount of pressure that the shoe (P) will apply to the ammunition (M)? This operation is carried out after the entire system is brought to the desired position, isn''t it? Answer 3 : It can be adjusted not only with a screwdriver but also with a wrench; it was designed this way to accommodate different equipment that may be accessible at the time. This adjustment process is used to pre-tension the bevel springs inside the shoes. Depending on the required ammunition type, this pre-tensioning is done only once. It is done before the ammunition is loaded.Question 4 : In order to fix the shoe (P) at the appropriate height for different ammunition (M) diameters, the operator rotates the latch belonging to the cam lever clamp, thereby clamping the adjustment shaft (3) and contributing to fixing the adjustment shaft (4) in the desired angular position… You had mentioned that the actual locking is provided by another element (At this point, I recall you saying that when the system is rotated, the bending of the fingertips while a finger presses on the ground creates the main pressure). It "contributes" to this locking. What is it that provides the actual locking?Answer 4: The inline position is only valid for one type of ammunition. For other ammunition types, the locking is performed by the clamp. In this inline position, after passing a certain point, the system cannot return to its previous position unless an external torque is applied. Let me try to explain the inline position as follows. When the system is initially in the /\ shape, coming to the -- position is the inline position. Moving a little further from here brings the system to a point from which it cannot return on its own.', '2026-05-23 16:46:03.29824', '2026-05-23 16:51:59.975734');
INSERT INTO public.inventor_qa VALUES (8, 10, 'Why Are Catadioptric Lenses Used?
•	Catadioptric lenses are used to provide extremely long focal lengths while requiring only a relatively short physical length of the lens. (US4523816)
•	A packaging problem can occur when the structure is made very long.
•	In the patent, the men/parts in the red on the left form the intermediate plane, but the inventor says that the red on the right is the actual intermediate plane.
•	If we make the G22 group on the right side mechanically attachable in a removable manner, then the appropriate lens group can be attached according to the aircraft''s mission need, enabling the imaging of a wavelength suited to that need.
•	Focusing = bringing the image into sharp focus.
•	The movable lens group provides the zoom function. (Two movable lens subgroups provide both focal length variation and focus adjustment)
•	(I think) the beam splitters set which wavelengths will pass in which direction.
•	Thanks to the intermediate image plane formed by the common mirror group—that is, by the common input—separating into wavelengths becomes easier. Thanks to this, if we wish, by placing a beam splitter cube or a filter behind the intermediate image plane, the system can be separated into visible, short-wave, or—if we wish—MWIR and LWIR wavelengths.
•	In addition, by changing the optical system we place behind the intermediate image plane, we can increase the zoom movement.
•	With "rotate-in-group," the lens group rotates and the lenses outside the circle move outside the beam boundaries. In other words, our rotating this mechanical system changes the focal length.
•	The beam splitter is used at the very beginning to separate into wavelengths.
•	The system most resembles a Schmidt-Cassegrain, but in that model it may be difficult to find a system with a lens at the rear. For this reason, the inventor recommends that I research it as catadioptric.
•	In the system there are 2 mirrors, and at the intermediate image plane there is a mirror or filter (this depends entirely on what benefits us in obtaining the patent); the rest are lenses. I can provide the materials of the lenses, but this may not be of any use.
•	Other than that, I have not currently planned anything in my mind regarding the motion mechanism.
•	It feels like we can also change that for the sake of patent writability.
', '2026-05-23 16:57:38.709996', '2026-05-23 16:59:49.760948');
INSERT INTO public.inventor_qa VALUES (10, 12, 'Question 1) When adjustment is being made on the orange pipe from Adjustment Zone 1 and Adjustment Zone 2, does the user, for example, position it at the desired angle from Adjustment Zone 1 and then connect it with the fasteners? Or does the user first place the pipe in some way from Adjustment Zone 1 and then rotate the pipe on the green part to bring it to the desired angle from Adjustment Zone 1 and then attach the fasteners? In other words, the question is: is the pipe attached to the green part already set at the desired adjustment from Adjustment Zone 1 before being attached to the green part, or is it first attached to the green part at some arbitrary angle and then rotated on the green part?
Answer 1) The orange part is first attached to the fixed green part. Afterward, the orange part is rotated to give it the desired angle. Finally, fastener assembly is carried out to fix the part at the adjusted angle.
Question 2) How do you measure the angles of the equipment and the pipes in the roll, pitch, and yaw axes, in degrees? By a mechanical method—if so, with which specific measuring instrument? Also, with which equipment and method could it be possible to measure this angle digitally? It will be useful for us to keep these possibilities in mind as well while writing the alternatives.
Answer 2) An "Alignment Procedure" is prepared for the equipment placement. Based on the equipment location in the 3D model, a two-dimensional "Board" is prepared, and an area is determined so as to cover the angles in the equipment installation requirement.
Afterward, this manufactured board is placed in front of the helicopter. By means of a laser placed on the part located in Adjustment Zone 2, it is checked whether the equipment falls within the specified area, and the desired angle adjustment is made using the adjustment zones.

', '2026-05-24 11:23:59.254025', '2026-05-24 11:27:20.563923');
INSERT INTO public.inventor_qa VALUES (11, 13, 'NAİM BEY MEETING NOTES 
•	The 2 fasteners at the rear are removed, then once contact is broken at the C-shaped tabs, the system disassembles. The 2 rear fasteners mentioned below are shown with a red arrow.
•	The problems we fundamentally solve and their benefits: the compactness benefit (there is a great deal of space constraint along the x, y, and z axes); we carry hydraulic pipes carrying high loads (3000 psi), so the load is very high. Our access constraint, again, is very significant along all 3 axes.
•	Our access to the fastener and the nut is very limited. For this reason, we use a nutplate for the nut, directly attached to the NC part (the same section as the place shown with the red arrow). In this way, we also achieve torquing merely by turning the fastener and merely having access to the fastener (thanks to our using a nutplate instead of a nut). (In the prior art documents, there is very broad access to the fastener and the nut, and none of them use a nutplate.)
•	If the fasteners shown with the red arrow fail, the system is held in the direction along the actuator by the fasteners shown with blue arrows in the image below; in addition, our C-section tabs also hold it.
•	In Boeing''s patent US10800540 — Transport Element Clamp System, there is no space constraint at all along the x, y, z axes; in particular, the axis along which the pipe extends lengthwise is wide open anyway. In our case, however, there is a compactness requirement along all 3 axes due to the nature of the system.
•	As an extra technical benefit of ours, we also have electrical isolation, a technical benefit that arises automatically due to our use of elastomeric material.
•	In addition, in the Boeing document, the system has to be lifted up and down by as much as the half-clamps when performing disassembly, whereas in our case there is not that much space.
•	The Boeing document also has slide-in attachment and clipping; the clipping system is quite similar to ours, and the inventor could not see a difference at that point because the slide-and-clip system follows the same logic everywhere.
•	Boeing''s document consists of huge NC parts, whereas we carry a very serious load of 3000 psi with only 3 thin-thickness NC parts.
•	None of the prior art has any concern regarding operation under high forces (3000 psi).
•	In addition, none of the prior art has fixing to the actuator itself, and—as in our invention—there is no concern regarding keeping stable those systems in which both, such as the actuator and the hydraulic pipe, have to move relative to each other (the actuator is constantly moving, because it is the control surface that actuates the rudder), while the pipes need to be routed quite stiffly, so they make relative movement with respect to each other.
•	In our case, the actuator and the pipes are surrounded by the rib; access is very problematic (shown in the images below).
•	We can assemble the system within itself with only 3 fasteners, whereas the prior art documents use a ton of fasteners.
•	The choice of the tabs being C-shaped is a preferential matter; in our case it is clearly a C, while in Boeing''s it is somewhat like an L—but that too can be considered roughly a C.
•	In Airbus''s DE patent, DE102010040446B4 — Device for mounting aircraft and spacecraft, there are again no high forces, and it does not even hold the pipe fully. The fact that the system consists of thin NC parts that are slid and held together to each other by clips is similar, but the holding of the pipe is not similar at all. It has no concern such as high forces at all.
•	In all the systems, fixed structures are always connected to each other. In our case, however, we connect the system to the non-fixed actuator.
•	Our disassembly is very different: we first turn the fastener in reverse and then slide it along the actuator axis; this movement continues for a while, but then—as can be seen in the image below—we can no longer slide it further, because there is no space along that axis either. We need to rotate it somewhat sideways in order to remove the system. Because if we do not do this, the system will strike the rib.
', '2026-05-24 11:29:58.649747', '2026-05-24 11:32:53.391134');
INSERT INTO public.inventor_qa VALUES (12, 14, 'Important Notes 
•	The reason this invention came about is that the flange structures indicated by 1a had to be raised upward due to space limitations (a packaging problem), resulting in the formation of an inverted-conical, reverse-sloped region. Because of the formation of this region, the stagnant oil volume marked in black is created. Our aim is to transfer this unusable oil to the sump so that it can rejoin the system, and—after it passes through various filters there—the stagnant oil rejoins the system again. In other words, this invention emerged in a situation where compactness is required and a packaging problem is experienced in the transmission. If compactness had not been a constraint, we would have made a downward-sloped cone and the oil would have flowed to the sump by gravity anyway.
•	If we had not done this, that oil would have remained there. For example, if the entire system needs 10 L of oil and the oil accumulating there is 1 L, then—because I cannot use my 1 L of stagnant oil in the system—I would have to put 11 L of oil into the helicopter instead of 10 L. And that means weight for me.
•	In addition, the stagnant oil accumulating there can reach the bearing during the sharp maneuvers the helicopter performs, through the movement of the fluid resulting from the maneuver, and can result in chips—which can be as small as even 0.1 mm—breaking the bearing. We are preventing this catastrophic effect.
•	If asked "Why didn''t you simply run a channel directly to the sump?"—there are 2 O-rings in between, so we cannot run a channel directly through that gap.
•	The oil at the main gear stage in the invention flows to the sump anyway. We transfer the stagnant oil coming from the oil at the 2nd and 3rd stages to the sump.
•	In the ATAK-2, because a rod has to pass through from below, the flanges needed to be raised upward. Indeed, the invention itself arose out of this necessity.
', '2026-05-24 11:35:00.041361', '2026-05-24 11:37:59.370094');


--
-- Data for Name: inventor_qa_document; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: patent; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.patent VALUES (9, 'Mechanical clamp and four-bar mechanism, swinging bracket specifically designed for different ammunition calibers.', 'TUSAS', '<h4>1. Description</h4>
<p>The present invention relates to an ammunition support system for air vehicles, specifically to a mechanical clamp and four‑bar mechanism that allows the sway brace shoes to be moved in a single plane while simultaneously ensuring that the sway‑brace shaft is held firmly – a feature not found in prior art.</p>
<p>Background of the art
A theory of … … .. ... We … .. … … … ..… … ..……… … &quot;… … …… ………………………………… ……………………‑…………………………………………… …… …...…….…………..……………………………………………………………………………… …… …...</p>
<h4>2. Claims</h4>
<p>Claim 1: (no text entered)</p>
<h4>3. Abstract</h4>
<p>The invention…</p>', '2026-05-23 16:46:00.515049', '2026-05-27 08:33:01.426798', 'Ammunition Support System', NULL);
INSERT INTO public.patent VALUES (14, 'Mechanism for draining oil from the stagnant oil region in the transmission', 'TUSAS', '<p style="margin:0 0 10px;">Click "Generate Draft"…wslwskw</p>', '2026-05-24 11:34:57.869735', '2026-05-27 16:40:56.765285', 'Load Carrying System', '');
INSERT INTO public.patent VALUES (13, 'Clamp Holder for Actuator Hydraulics', 'TUSAS', '<h4>1. Description</h4>
<p>The present invention relates to a clamp holder for actuator hydraulics, more particularly to a compact and efficient clamp holder that secures multiple hydraulic transmission lines within the rudder direction of an aircraft flight control system.</p>
<p>In conventional flight‑control systems, hydraulic supply lines are required by many components. Standard hydraulic clamps are employed to secure these lines to actuators; however, such clamps occupy substantial volume in the confined region around the actuator and increase procurement cost and assembly time. When the transmission lines extend away from the actuator, they sweep a larger area, leading to heavier structural parts and making routing difficult in narrow spaces. Traditional clamp designs typically use separate clamps for each pipe, which exacerbates tolerance accumulation and causes incorrect routing.</p>
<p>The present invention overcomes these disadvantages by providing a single clamp holder that can secure multiple hydraulic pipes located on the actuator. The design incorporates elastomeric material within the clamp‑holder part to prevent corrosion, wear, heat transfer and electrical conduction. Because the clamp holder occupies less volume, it allows routing as close as possible to the equipment, thereby eliminating access problems. Moreover, the clamp‑holder is assembled by sliding, permitting disassembly or assembly from a single direction by a single operator.</p>
<p>The clamp holder comprises a Body (2) positioned within the rudder direction and a Transmission line (3) that generates mechanical force from contained fluid. An Actuator (4) moves the fluid within the transmission line. The clamp holder includes a First holder (5) and a Second holder (6) which together secure the Transmission line (3). A Fastener (7) is mounted on an Extension (10); the Extension (10) is perpendicular to the line and actuator‑mounted, while the Flange (9) is parallel to the line. The Flange (9) faces the transmission line and is designed for load‑carrying hydraulic applications.</p>
<p>A Bearing element (8), which is flexible, is positioned between the holders and the flanges to accommodate minor misalignments and to reduce wear. A Latch (11) engages with the Transmission line near the flange to maintain secure positioning during operation. The clamp holder thus provides a single‑piece solution that secures multiple hydraulic lines while minimizing volume, preventing corrosion and wear through elastomeric material, and enabling simple sliding assembly from one direction.</p>
<p>In summary, the invention offers an efficient, compact, and reliable clamp holder for actuator hydraulics that addresses the limitations of prior art by combining multiple hydraulic pipes into a single clamp, employing elastomeric materials to mitigate environmental effects, allowing close routing to equipment, and facilitating straightforward assembly and disassembly.</p>
<h4>2. Claims</h4>
<p>Claim 1: Clamp Holder for Actuator Hydraulics comprising a Body (2), positioned within the rudder direction; characterized in that the Clamp Holder for Actuator Hydraulics further comprises a Transmission line (3), generating mechanical force from contained fluid.</p>
<p>Claim 2: Clamp Holder for Actuator Hydraulics according to claim 1, further comprising an Actuator (4), moving the fluid within the transmission line.</p>
<h4>3. Abstract</h4>
<p>The invention provides a compact clamp holder for actuator hydraulics that secures multiple hydraulic transmission lines within the rudder direction of an aircraft flight‑control system. The clamp holder comprises a body positioned around the actuator, a transmission line that conveys fluid pressure, and an actuator that moves said fluid. Two holders cooperate to secure the transmission line, while a fastener mounted on an extension perpendicular to the line and a flange parallel to the line provide load‑carrying capability. A flexible bearing element is interposed between the holders and flanges to accommodate minor misalignments and reduce wear. An elastomeric material within the clamp holder prevents corrosion, heat transfer, electrical conduction, and wear. The design allows sliding assembly from a single direction, enabling simple disassembly or installation by one operator while minimizing volume and routing complexity.</p>', '2026-05-24 11:29:53.241501', '2026-06-03 13:58:52.691744', 'Clamp Assembly', '');
INSERT INTO public.patent VALUES (10, 'Catadioptric Multi FoV and Multi Wavelength Optical System', 'TUSAS', '<h4>1. Description</h4>
<p>[This section could not be generated — check the LLM connection and try again.]</p>
<h4>2. Claims</h4>
<p>Claim 1: Catadioptric Multi FoV and Multi Wavelength Optical System comprising a Catadioptric lens system (S), providing very long focal lengths while remaining physically compact; characterized in that the Catadioptric Multi FoV and Multi Wavelength Optical System further comprises a Primary mirror (1), forming the intermediate image plane.</p>
<p>Claim 2: Catadioptric Multi FoV and Multi Wavelength Optical System according to claim 1, further comprising an Image group (D), forming an intermediate image plane.</p>
<h4>3. Abstract</h4>
<p>[This section could not be generated — check the LLM connection and try again.]</p>', '2026-05-23 16:57:34.113236', '2026-06-03 17:24:00.527308', 'A Catadioptric Lens System for Aircraft', NULL);
INSERT INTO public.patent VALUES (12, 'Adjustable Pipe Mounting Design for Exterior Region Equipment', 'TUSAS', NULL, '2026-05-24 11:23:57.408579', '2026-05-24 11:23:57.408579', 'Adjustable Equipment Mounting System', NULL);


--
-- Data for Name: research_report; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.research_report VALUES (6, 9, 'Although the prior art includes sway brace shoes whose positions can be changed for different ammunition diameters, these systems are complex, consisting of many parts, and are heavy. Furthermore, the range of different ammunition diameters that can be fitted to the system is limited due to the planes in which the sway brace shoes can move in the prior art.
With the invention in question, the technician can change the shoe positions from a single point by inserting an allen key into the allen hole and rotating the hexagonal profile via the four-bar mechanism by turning the allen key. Thanks to the system consisting of a four-bar mechanism, the system is relatively simpler, lighter, and less prone to failure. Furthermore, since the four-bar mechanism is positioned along the vertical plane when the aircraft is viewed from the front, the shoes can only move in this plane, which allows the shoes to change position over a wider range of ammunition diameters compared to the prior art. Thus, ammunition can be fitted to the system over a much wider range of ammunition diameters.

The elements of the invention are as follows:

1.	Changing the sway brace positions for different ammunition diameters by means of a four-bar mechanism.

2.	Moving the shoes only in the vertical plane by positioning the four-bar mechanism of the sway brace shoes along the vertical plane when the aircraft is viewed from the front.
3.	Contributing to fixing the system in the desired position specifically for the sway brace by means of a mechanical clamp such as a saddle.
4.	Connecting the 2 four-bar mechanisms containing the shoes to the mechanical clamp not as a single integral assembly, but as 2 separate sub-assemblies.

5.	The first bar part of the four-bar mechanism containing a structural stopper part that limits the angular range of the system.
6.	The technician actuating the movement of the sway braces by rotating the four-bar mechanism via the allen hole using an allen key.

With reference to Articles 56 and 54 of the European Patent Convention, when the present invention is evaluated by taking into account the prior art obtained as a result of the conducted research, it has been concluded that elements 1 and 2 set forth in the invention disclosure contain novelty and inventive step, elements 3 and 5 contain novelty but do not contain inventive step, and elements 4 and 6 do not contain novelty or inventive step. The final decision will be made by the intellectual property board.', NULL, NULL, '1.	CHANGİNG THE SWAY BRACE POSİTİONS FOR DİFFERENT AMMUNİTİON DİAMETERS BY MEANS OF A FOUR-BAR MECHANİSM

In the 1983 patent document numbered 4620680A, titled "Device for Carrying and Ejecting Under Aircraft Loads, Comprising Support Arms Positioned with Respect to the Diameter of the Loads"; a device is mentioned in which the sway brace positions can be changed for loads of different diameters. The position change of the sway braces is achieved by means of a bevel gear (20) and a cam (11). Synchronized movement of the sway braces on both sides is ensured by means of a rotating shaft (24).  In the 1980 patent document numbered US4395003A, titled "Device for Suspending Under Aircraft Miscellaneous Loads with Variable Distance Between Centers"; a device is mentioned that carries various aircraft loads with a variable distance between centers. The adjustment of the distance between centers is achieved by moving the mechanism by means of a cam (18) and rotating it clockwise or counterclockwise as a result of the gear sets (13, 16) meshing with each other.In the 1977 patent document numbered US4122754A, titled "Dependent Sway Bracing Weapon Restraints"; a dependent sway brace ammunition restraint is mentioned. The actuation of the sway braces, which are connected to each other by a cam (16), and the change of their positions are achieved by means of a rack-pinion mechanism. In this way, sway braces that can automatically adapt to different ammunition sizes are provided by the mechanism. When the documents in the prior art are examined, element  1 contained in the invention disclosure form contains novelty and inventive step. In the 2018 patent document numbered EP3636547B1, titled "Restrain and Release Mechanism for an Externally Airborne Load"; a mechanism for restraining and releasing an externally airborne load is mentioned. The mentioned mechanism includes a monolithic metal body produced by additive manufacturing method and a damping layer made of elastomeric material. In this way, the mechanism is ensured to flex on different ammunition and the sway brace is ensured to apply equal pressure to the ammunition. The plate-like elements (3) are damping elements made of elastomeric material. With the mechanism; the monolithic metallic structure can deform not only following compression, but also following rotations perpendicular to the load direction, can eliminate possible misalignments or geometric irregularities, and can guarantee the same pressure over the entire surface designated for contact.2.	MOVİNG THE SHOES ONLY İN THE VERTİCAL PLANE BY POSİTİONİNG THE FOUR-BAR MECHANİSM OF THE SWAY BRACE SHOES ALONG THE VERTİCAL PLANE WHEN THE AİRCRAFT İS VİEWED FROM THE FRONT  In the 1970 patent document numbered US3670620A, titled "Automatic Sway Brace Device"; an automatic sway brace device is mentioned. The shoes can move along the planes shown with red lines in Figure 7. This allows a range of different ammunition diameters to be fitted to the system. In our invention disclosure, however, it is more advantageous compared to the relevant document, as a much wider range of different ammunition diameters can be fitted to the system thanks to the feature of the shoes being able to move along the vertical plane when the aircraft is viewed from the front. There are also other documents in the prior art that provide positional change of shoes along similar lines. When the relevant section is examined, element -2 contains novelty and inventive step.3.	CONTRİBUTİNG TO FİXİNG THE SYSTEM İN THE DESİRED POSİTİON SPECİFİCALLY FOR THE SWAY BRACE BY MEANS OF A MECHANİCAL CLAMP SUCH AS A SADDLESİNCE NO RELEVANT DOCUMENT HAS BEEN FOUND İN THE PRİOR ART, ELEMENT  3 CONTAİNS NOVELTY, HOWEVER, AS İT İS CONSİDERED OBVİOUS TO A PERSON SKİLLED İN THE ART, İT DOES NOT CONTAİN İNVENTİVE STEP.4.	CONNECTİNG THE 2 FOUR-BAR MECHANİSMS CONTAİNİNG THE SHOES TO THE MECHANİCAL CLAMP NOT AS A SİNGLE İNTEGRAL ASSEMBLY, BUT AS 2 SEPARATE SUB-ASSEMBLİES
By connecting the 2 four-bar mechanisms containing the shoes to the mechanical clamp not as a single integral assembly, but as 2 separate sub-assemblies, the system is made suitable for different needs and ease of maintenance is achieved. The 2 separate sub-assemblies are connected to the mechanical clamp as shown by the red arrows. In the 2014 patent document numbered US10518883B2, titled "Small Store Suspension and Release Unit"; an adjustable unit with sway braces for different ammunition diameters is mentioned. The center bracket (64) contains a lead screw (88) threaded in opposite directions at each end. The actuator nut (46) is mounted to the lead screws (88) with threads. The lead screw (88) can rotate the end portions (90) with a wrench or a hexagonal head allen key. By rotating the mentioned parts, the sway brace legs (20) move up and down, thereby providing rotation around the C-shaped guide channels (66), and the sway braces can be adjusted for different ammunition diameters. When the relevant section is examined, element  4 does not contain novelty or inventive step.THE FİRST BAR PART OF THE FOUR-BAR MECHANİSM CONTAİNİNG A STRUCTURAL STOPPER PART THAT LİMİTS THE ANGULAR RANGE OF THE SYSTEMBy means of the first bar part of the four-bar mechanism containing a structural stopper part that limits the angular range of the system, the different ammunition diameter range is predetermined by the user and further movement of the system is prevented. Since no relevant document has been found in the prior art, element  5 contains novelty, however, as it is considered obvious to a person skilled in the art, it does not contain inventive step.6.	THE TECHNİCİAN ACTUATİNG THE MOVEMENT OF THE SWAY BRACES BY ROTATİNG THE FOUR-BAR MECHANİSM VİA THE ALLEN HOLE USİNG AN ALLEN KEY.By the technician actuating the movement of the sway braces by rotating the four-bar mechanism via the allen hole using an allen key, and thereby being able to change the positions of the shoes, an easy adjustment capability for changing the shoe positions is provided.  In the 1943 patent document numbered GB577186A, titled "Improvements Relating to Bomb Carriers for Aircraft"; a mech
anism is mentioned that allows the user to adjust both shoes simultaneously by rotating the short shaft element (i). In the mentioned mechanism, by rotating the short shaft (i), the shoes on both sides can be moved simultaneously by means of worm gears (g, h). In this way, sufficient stability for the bomb is ensured. In the 1970 patent document numbered US3670620A, titled "Automatic Sway Brace Device"; an automatic sway brace device is mentioned. The rotation of the shaft (22) closes and opens the distance between the clamps (26). This causes the sway braces (15) to displace symmetrically with respect to the rack (10). Pre-tension is defined to the system by rotating the limit nut (25). It is also mentioned that the relative distance between the shoes and the lugs at the ends of the sway braces is changed by means of turnbuckles.In the 2014 patent document numbered US10518883B2, titled "Small Store Suspension and Release Unit"; an adjustable unit with sway braces for different ammunition diameters is mentioned. The center bracket (64) contains a lead screw (88) threaded in opposite directions at each end. The actuator nut (46) is mounted to the lead screws (88) with threads. The lead screw (88) can rotate the end portions (90) with a wrench or a hexagonal head allen key. By rotating the mentioned parts, the sway brace legs (20) move up and down, thereby providing rotation around the C-shaped guide channels (66), and the sway braces can be adjusted for different ammunition diameters. When the documents in the prior art are examined, elementr 6 does not contain novelty or inventive step. 
', '2026-05-23 16:46:03.372966', '2026-06-03 11:47:48.29003');
INSERT INTO public.research_report VALUES (9, 12, 'In the prior art, in the case of equipment found on the Cobra AH-1-F helicopter and in the exterior regions of other aircraft, whose placement must be carried out precisely, there can be situations where the required precision cannot be achieved through manufacturing tolerances. In such cases, because the need to make an adjustment arises after equipment installation, the equipment placement design must be carried out in a manner compliant with the requirements. Within the scope of the Bahrain Cobra Modernization (BCM) Project, the placement requirements of the Helicopter Air Data System (HADS) equipment are such that the installation must be at a precision of ±0.5 degrees in the pitch, roll, and yaw angles. Achieving these values through manufacturing tolerances both makes the processes complex and increases the manufacturing cost. For this reason, the necessity of making an adjustment after equipment installation arises.
With the invention in question, a design of 2 pipes that have different axes of rotation and fit one inside the other has been made for equipment installation. By means of the slots located on these two pipes, the angles can be changed by rotating these pipes. With Adjustment Zone 1, the possibility of making adjustments in the roll and yaw angles is provided. With Adjustment Zone 2, the possibility of making an adjustment in the pitch angle is provided. With these adjustment capabilities, the precise angle requirements found in the equipment requirements can be met. The invention proposal is used in the Cobra AH-1-E model.
The elements included in the invention are as follows:
1.	The ability to make the pitch, roll, and yaw angle adjustments of the equipment, by means of bringing the pipes and equipment to the desired positions and angles—via the radially positioned channels (slots) located at certain intervals on one another—of the 2 pipes that fit one inside the other, from Adjustment Zone 1, for equipment installation.
2.	The adjustment of the equipment pitch angle by bringing the pipe and the adapter to the desired position—via the radially positioned channels (slots) located at certain intervals on one another—from Adjustment Zone 2.
3.	The ability of the yaw, pitch, and roll angles to also change when the yaw angle is adjusted from Adjustment Zone 1, by means of the 2 pipes rotating about an axis predetermined by the user, which is inclined to the right in the helicopter front view and inclined to the right in the helicopter side view.Pursuant to Articles 56 and 54 of the European Patent Convention, when the present invention is evaluated by taking into account the prior art obtained as a result of the research conducted, it has been concluded that the 1st, 2nd, and 3rd elements included in the invention disclosure contain novelty and an inventive step. The final decision will be made by the Intellectual Property Rights Board.
', NULL, NULL, 'Element 1
The ability to make the pitch, roll, and yaw angle adjustments of the equipment, by means of bringing the pipes and equipment to the desired positions and angles—via the radially positioned channels (slots) located at certain intervals on one another—of the 2 pipes that fit one inside the other, from Adjustment Zone 1, for equipment installation.The patent document US10048103B2, titled "Adjustable Position Pitot Probe Mount," dated 2018 and belonging to Bell Helicopter Textron Inc., describes a pitot tube mount at a changeable position. The invention includes an adjustable Pitot tube and a method for using it for the operation or flight testing of an aircraft, comprising the following: a Pitot probe; a streamline tube connected to the Pitot probe; a socket connected to the streamline tube on the aircraft, where the streamline tube is a socket in which at least one can rotate about an axis of the connection, or in which the streamline tube can move the Pitot probe closer to or farther from the surface of the aircraft. The second method, together with the telescoping feature, allows adjustments in all directions achieved via a spherical joint to the aircraft, with the spherical joint allowing rotation in every direction. The telescopic feature allows the sensor to move in/out relative to the aircraft. By combining the telescoping feature with the spherical feature, any orientation of the Pitot probe can be achieved.Element 2
The adjustment of the equipment pitch angle by bringing the pipe and the adapter to the desired position—via the radially positioned channels (slots) located at certain intervals on one another—from Adjustment Zone 2.
Since no relevant document could be found in the prior art for the 2nd technical element, it has been assessed that Element 2 contains novelty and an inventive step.Element 3
The ability of the yaw, pitch, and roll angles to also change when the yaw angle is adjusted from Adjustment Zone 1, by means of the 2 pipes rotating about an axis predetermined by the user, which is inclined to the right in the helicopter front view and inclined to the right in the helicopter side view.

Since no relevant document could be found in the prior art for the 3rd technical element, it has been assessed that Element 3 contains novelty and an inventive step.


', '2026-05-24 11:23:59.256042', '2026-05-24 11:27:22.234041');
INSERT INTO public.research_report VALUES (11, 14, 'In the prior art, the slip-fit flange section (1a) that provides the cluster casing (cap, cover)–main housing connection has been moved upward in the vertical direction, thereby reducing the volume used by the transmission in the vertical direction. However, the disadvantage created by this application is that, when the base of the cluster casing is angled (1b), oil accumulates in the resulting conical volume. Oil flowing from the lubricated gear mesh point and from the bearings accumulates at the base of the cluster casing (1b). Normally, oil flow is expected to go directly to the sump by gravity without accumulating in any region. The oil reaching the sump must pass through the chip detector and then be pressurized. However, in this design, this accumulated oil is both carried in the aircraft as extra weight, and—because it does not enter the chip detector—it carries the potential to accumulate chips. Chips accumulated in the oil reaching the rotating transmission elements as a result of a maneuver could have a catastrophic effect.
With the invention in question, the likelihood of the accumulated excess oil adding extra weight to the aircraft, creating a chip-accumulation potential, and reaching the rotating transmission elements during maneuvers and creating a catastrophic effect is reduced. One or more buckets rotating together with the gear help drain the oil accumulating at the base by means of the centrifugal effect. Thanks to the openings (9) in the cluster casing, the circulating oil is flung outward and then passes through a window-shaped opening (10), directing it toward the sump (11). As an alternative to the bucket structure that flings the oil outward by the vortex (centrifugal) effect, one or more flat plates (12) can be used. In addition, for the same flow-directing purpose, more streamlined concave or convex vanes (13) can be used. The vanes (12, 13) can be connected to the gear individually, or they can be placed on a common ring and connected to the gear as a single unit. The openings (9) in the cluster casing can be designed as flow-directing channels (14). In this way, the channel walls both serve as a structural element carrying the bearings above them and ensure that the flow is directed outward and reaches the sump (11) by passing through the window (10).
The elements included in the invention are as follows:
Element 1.	The presence of at least one bucket structure located all the way around at the bottom point of the gear or at the lock nut—alternatively, one or more flat plates or vane structures connected to the gear—and these structures functioning as a pressurizing element in a flow-friendly manner by means of the centrifugal effect for the discharge of oil.
Element 2.	The presence of openings (9) in the cluster casing—preferably, additionally, the opening in the cluster casing being able to be designed as a flow-directing channel (14)—and, thanks to the placement of streamlined blades integral with the cluster casing, the oil passing through the flow-pressurizing elements in Element 1 (bucket, flat plate, or vane) subsequently passing through the flow-directing channels to be delivered to the sump more efficiently (with less power loss).
Element 3.	The oil being transferred to the sump after passing, respectively, through the openings (9 or 14) in the cluster casing and then through a window-like opening (10) in the main housing, thereby enabling the stagnant oil to rejoin circulation.
Pursuant to Articles 56 and 54 of the European Patent Convention, when the present invention is evaluated by taking into account the prior art obtained as a result of the research conducted, it has been concluded that the 1st, 2nd, and 3rd elements included in the invention disclosure contain novelty and an inventive step. The final decision will be made by the Intellectual Property Rights Board.', NULL, NULL, 'Element 1
The presence of at least one bucket structure located all the way around at the bottom point of the gear or at the lock nut—alternatively, one or more flat plates or vane structures connected to the gear—and these structures functioning as a pressurizing element in a flow-friendly manner by means of the centrifugal effect for the discharge of oil. The patent document EP2690318B1, titled "Direct drive rotation device for passively moving fluid," dated 2012 and belonging to Bell Helicopter Textron Inc., describes a geared fluid pump intended to passively move oil taken from the sump upward against the direction of gravity. The fluid exits the bearing seat opening and is directed toward a part resembling a threaded shaft. Here there are "ears" structures, which direct the fluid into the threaded shaft. The threaded shaft rotates and, by the effect of centrifugal force, directs the fluid toward the bearing seat opening above. The patent document US8464835B2, titled "Lubricant Scoop," dated 2008 and belonging to Rolls-Royce Corporation, describes a lubricant scoop. It describes a structure in which a lubrication spray is taken in and the collected oil is directed axially and radially with respect to the axis of rotation. It includes an upstream opening (28) that allows the oil coming from the lubrication nozzle (30) to pass through the entry plenum (26). There are teardrop-shaped structures located all the way around a rotating shaft that direct the lubrication flow axially and radially. The most efficient way to lubricate high-speed bearings was found to be the oil entering from the inside diameter (ID) and spreading radially outward by the effect of high G-force; in this context, the lubrication scoops perform this function. The lubrication scoops provide oil direction when the structures adjacent to the rotating shaft are inaccessible, or when the open end of the shaft is larger than the radius of the component to be lubricated. The patent document CN111503253A, titled "Lubricating Structure of Transmission Mechanism," dated 2020 and belonging to Hunan Aviation Powerplant Research Institute AECC, describes the lubricating structure of a transmission system. It describes that the oil-throwing structure (420) can throw oil from the oil pool to the inlet flow channel (310). It describes that the oil-throwing structure (420) consists of blades located all the way around the rotating shaft at equal intervals. First, the oil passing through the oil inlet flow opening (310) rises by the effect of centrifugal force and passes through the second oil hole (320). The oil passing through the first oil hole (110) flows to the oil return flow opening (110). And as a result, the oil passing through the oil return flow opening (110) flows to the oil pool against the effect of gravity. During backward-flow lubrication, the lock structures are lubricated. In addition, metal chips generated by the lock structures during backward flow are discharged together, thereby preventing secondary wear. When the prior art documents are evaluated, Element 16 contains novelty and an inventive step. Element 2
The presence of openings (9) in the cluster casing—preferably, additionally, the opening in the cluster casing being able to be designed as a flow-directing channel (14)—and, thanks to the placement of streamlined blades integral with the cluster casing, the oil passing through the flow-pressurizing elements in Element 1 (bucket, flat plate, or vane) subsequently passing through the flow-directing channels to be delivered to the sump more efficiently (with less power loss).The patent document CN205101532U, titled "Tail reduction gear and pitch control rod bearing lubricating structure thereof," dated 2015 and belonging to China Aircraft Power Machinery Institute, describes the lubrication of a tail gear and a pitch-control rod bearing. The oil moves in the directions shown in red; oil is transferred from the oily pocket (17) toward the shaft, and from the shaft it moves backward again through the second oil holes (50), enabling the oil to reach the bearings. When the prior art documents are evaluated, Element 2 contains novelty and an inventive step.Element 3
The oil being transferred to the sump after passing, respectively, through the openings (9 or 14) in the cluster casing and then through a window-like opening (10) in the main housing, thereby enabling the stagnant oil to rejoin circulation.The patent document US2016369887A1, titled "Lubrication Systems for Gearbox Assemblies," dated 2016 and belonging to Sikorsky Aircraft Corporation, describes a lubrication system for gearbox assemblies intended to keep lubrication continuing during helicopter emergencies. Oil flowing along a first flow path between the transmission element and the crankcase is collected in the reservoir in question, and through a second flow path it is stored within the housing, creating an oil source. The oil collection process can also be carried out by means of a sheet-metal or thin-walled circular pan placed beneath the gearbox drive gears. When the prior art documents are evaluated, Element 3 contains novelty and an inventive step.


', '2026-05-24 11:35:00.040051', '2026-06-03 11:41:29.228891');
INSERT INTO public.research_report VALUES (10, 13, 'In the prior art, because clamps generally consist of 2 block parts, there is a high volume requirement, compactness cannot be achieved, and additionally the clamp system has a high weight. In addition, for similar reasons, assembly/disassembly activities are quite difficult in areas where technician access is challenging/limited, and in some cases not possible; additionally, two-block-part clamps remain far from the surface to which they are fixed and cause incorrect routing due to tolerance accumulation.
With the invention in question, because the system has a design close to the actuator surface to which it will be fixed, the routing error is reduced, and a compact design that occupies less volume is achieved. Because there is elastomeric material in the clamp-holder part, the system is resistant to effects such as corrosion, wear, heat, etc. Assembly can be performed by sliding; in this way, assembly/disassembly can be performed from a single direction by a single person outside the aircraft, and additionally this prevents the possibility of the other structural parts of the aircraft being damaged during assembly/disassembly. Because the system is one exposed to vibration and the load flow will be through the structure rather than through the pipes, there will be no need to replace the pipes throughout their service life. The invention in question provides a solution as a clamp system that holds high-pressure hydraulic pipes, particularly for designs that have volume constraints along the x, y, and z axes.
The elements included in the invention are as follows:
1.	A clamp consisting of three parts—an upper half, a lower half, and an interface part—comprising: the upper-half part formed by a ceiling, a side flange, and upper-tab portions in the form of protrusions; the lower-half part formed by a base, a side flange, and a lower tab that is in the form of a protrusion and, by virtue of having a form conjugate with the upper tab, interlocks with it; and the ceiling and side-flange portions forming the interface.
2.	The presence, in the clamp-holder part, of an elastomeric material in the form of two half-circles—one in a lower part and one in an upper part—that wraps the pipe all the way around, so as to be form-compatible with the cylindrical geometry that is the pipe geometry.
3.	The preference for a nutplate as the nut, due to the very limited access to the fastener and particularly to the nut, and the nutplate being pre-installed on the system.
4.	In the event that the first fastener group fails, the second fastener group continuing to hold the system functionally along the direction in which the actuator extends lengthwise.Pursuant to Articles 56 and 54 of the European Patent Convention, when the present invention is evaluated by taking into account the prior art obtained as a result of the research conducted, it has been concluded that the 2nd element included in the invention disclosure does not contain novelty and an inventive step, that the 1st element does contain novelty and an inventive step, and that the 3rd and 4th elements contain novelty but do not contain an inventive step. The final decision will be made by the Intellectual Property Rights Board.
', NULL, NULL, 'Element 1
A clamp consisting of three parts—an upper half, a lower half, and an interface part—comprising: the upper-half part formed by a ceiling, a side flange, and upper-tab portions in the form of protrusions; the lower-half part formed by a base, a side flange, and a lower tab that is in the form of a protrusion and, by virtue of having a form conjugate with the upper tab, interlocks with it; and the ceiling and side-flange portions forming the interface.
In this way, the routing error in the system is reduced and the system occupies less volume. The routing will come as close as possible to the equipment, so routing will be carried out more accurately. In addition, thanks to the design, assembly can be performed by sliding and while outside the aircraft. Thus, assembly/disassembly can be performed from a single direction by a single person. The possibility of the other structural parts of the aircraft being damaged during assembly/disassembly is prevented. Because the system is one exposed to vibration and the load flow will be through the structure rather than through the pipes—via fasteners attached from the ceiling to the actuator—there will be no need to replace the pipes throughout their service life. In addition, due to our space constraint along the x, y, and z axes, thanks to our system design, system disassembly is as follows: first, the first fastener group (shown with a red arrow in Element 4) is turned in reverse, and then the system is slid along the actuator axis; this movement continues for a while, but then, due to the space constraint resulting from the limited distance to the rib, the system continues to be slid only until it approaches the rib. Then, to complete the disassembly, the system needs to be rotated somewhat sideways about the first fastener group. If the rotation movement is not performed, there is a risk of the system striking the rib.The patent document US10800540, titled "Transport Element Clamp System," dated 2020, describes a transport element clamp system for aircraft applications. The system includes a lower portion and an upper portion that can create a gap between two support structures in an aircraft and can lock together. The lower and upper portions also have recesses that form a channel system to receive transport elements. The system is designed to electrically isolate the transport elements from the support structures in order to comply with safety regulations. The system simplifies the assembly process by eliminating the need for cover seals and reducing the number of parts required. The locking mechanism (310) is shown with a bracket (438) connected to a clip (440). On the other side of the transport element clamp system (300), the locking mechanism (500) also locks the upper portion (302) to the lower portion (304). The locking mechanism (500) has a bracket (502) and a clip (504). The bracket (502) is snap-fitted; it is attached to the clip (504) to further secure the upper portion (302) to the lower portion (304). The lower portion (222), the upper portion (224), and the additional part (234) consist of a dielectric material (250). The dielectric material (250) may consist of at least one material selected from a thermoplastic material, a thermoset material, acetal homopolymer, or nylon. Polytetrafluoroethylene, polyamide-imide, graphite, carbon-fiber-reinforced plastic, melamine, phenolic and other resins (with or without reinforcing fibers), polyetheretherketone (PEEK), polyetherketoneketone (PEKK), rubber, or other suitable electrically insulating material may be selected. In Figure 11, a drawing of an aircraft cross-section showing the components of a transport element clamp system is shown in accordance with an illustrative arrangement. In this example, the upper portion (302) has been slid in the direction of arrow (1012) to fit into place. Fasteners can be used to fix the transport element clamp system (300) as a whole to beam (1006) and beam (1008). In the document in question, similar to the invention, slide-in attachment and clipping are present. However, in the patent in question, unlike the invention, it is seen that there is no space constraint at all along the x, y, z axes; in our invention, there is a compactness requirement along all 3 axes. In addition, in the document in question, there is a requirement for the system to be lifted up and down by as much as the half-clamps during disassembly, whereas in our system this much space is not available. In addition, the document in question consists of volumetrically large block parts, whereas in our invention a very serious pressure load of 3,000 psi is carried with only 3 thin NC parts. In addition, in the invention in question, no technical concern such as relative movement of the actuator and the pipes with respect to each other was pursued. In our invention, the technical concern in question was pursued and the system permits it. In addition, while in all the prior art documents long and quite numerous fasteners are used, in our invention the system can be assembled within itself with only 3 fasteners. In addition, the system does not pursue any concern about there being any relative movement between the pipe and the actuator.The patent document DE102010040446B4, titled "Device for mounting systems and aircraft and spacecraft with this device," dated 2012, describes an apparatus for support systems such as fluid-carrying or electrical lines in an aircraft or spacecraft structure. The apparatus includes a one-piece base support and a system holder that can be attached to the base holder to hold the systems. Both holders have two different locking devices that provide easy attachment and greater safety. The invention aims to provide a flexible and easy-to-install device that can reliably hold systems under long-term vibrations and high forces. To reduce manufacturing costs, the use of threaded connections is avoided and the connection process is simplified. For this purpose, the other base holder (3c) is first in a staggered position relative to the second base holder (3b) in a longitudinal direction, in the direction of arrow (19) such that its side surface (10) is formed relative to the side surface (10) of the second base holder (3b); the connecting element 14 in recess 18 (not marked in Figure 4, but visible in Figure 3). Then the other base holder (3c) is slid in the direction of arrow (20) largely along the longitudinal direction (L). It is a perspective view of a system holder (107) of a mounting part (128) for a device according to a second example arrangement of the invention. The connecting section (128) according to the second embodiment differs from the connecting part (28) according to the first embodiment, because two locking elements (139) with elastically bendable sections (140) are now provided. The locking elements (139) rest, in the second example arrangement, of a T-shaped protrusion (130) having holding sections (132) and longitudinal grooves (135) on one side. Although the system, similar to our invention, has a sliding movement and clipping, unlike our invention, because high pressures are not carried in the system, the holder does not hold the pipe so as to wrap it all the way around. In addition, the system does not permit relative movement of the pipe. In addition, there is no space constraint along the longitudinal axis of the system.
When the relevant section is examined, it has been assessed that Element 1 contains novelty and an inventive step.Element 2
The presence, in the clamp-holder part, of an elastomeric material in the form of two half-circles—one in a lower part and one in an upper part—that wraps the pipe all the way around, so as to be form-compatible with the cylindrical geometry that is the pipe geometry.
In this way, the system becomes resistant to effects such as corrosion, wear, heat, etc. The patent document US2404531, titled "Conduit Supporting Block," dated 1943, describes a sectional block-like support for holding a group of pipelines in place in an aircraft. The support is made of rigid material and is equipped with flanges to facilitate the mounting of cushion strips made of rubber or synthetic rubber that dampen vibrations and protect the lines against wear. The improved body construction of the support block consists of half-sections pressed or molded from metal or plastic material, which reduces the manufacturing cost and pre-forms the cushion-retaining flanges on them. The invention provides an improved pipe support block that is lightweight, cost-effective, and can securely hold the cushioning strips in place, thereby reducing damage to the pipelines and improving the overall safety and efficiency of the aircraft.
When the relevant section is examined, it has been assessed that Element 2 does not contain novelty and an inventive step.Element 3
The preference for a nutplate as the nut, due to the very limited access to the fastener and particularly to the nut, and the nutplate being pre-installed on the system.
In this way, it is ensured that the technician, while assembling the system, only has access to the fastener, and that the assembly and disassembly of the system can be performed by turning the fastener.
No document related to the relevant element was found. It has been assessed that the relevant element contains novelty, but that—when evaluated in terms of obviousness to a person skilled in the art—element 3 does not contain an inventive step.Element 4
In the event that the first fastener group fails, the second fastener group continuing to hold the system functionally along the direction in which the actuator extends lengthwise.
In this way, it is ensured that, in the event the first fastener group fails while the aircraft is flying, the second fastener group continues the fully functional operation of the system until the aircraft lands.No document related to the relevant element was found. It has been assessed that the relevant element contains novelty, but that—when evaluated in terms of obviousness to a person skilled in the art—element 4 does not contain an inventive step.





', '2026-05-24 11:29:58.647735', '2026-06-03 11:44:08.668746');
INSERT INTO public.research_report VALUES (7, 10, 'In the prior art, catadioptric lenses can be used to provide extremely long focal lengths while requiring a relatively short physical length of the lenses/optical system compared to other optical types. Because any protrusion on the aircraft surface creates an adverse aerodynamic effect, and because the use of heavy structures on the aircraft is not preferred, catadioptric lenses are lens structures suitable for use on aircraft. Through the use of these structures, an advantage is provided specific to the optical system in terms of packaging and weight for the aircraft. For the aircraft, it would provide a great advantage to realize the design of an optical system that can be used effectively for different mission profiles such as air/air and air/ground, that can perform detection in multiple wavelengths (visible, near-infrared (NIR), mid-infrared (MWIR), long-infrared (LWIR)) so that effective imaging can be provided in different environmental conditions such as light and dark weather conditions, and thereby has the ability to view targets clearly and at different angles for environmental awareness.
With the invention in question, a design of an optical system has been realized for the aircraft that can be used effectively for different mission profiles such as air/air and air/ground, that can perform detection in multiple wavelengths (visible, near-infrared (NIR), mid-infrared (MWIR), long-infrared (LWIR)) so that effective imaging can be provided in different environmental conditions such as light and dark weather conditions, and thereby has the ability to view targets clearly and at different angles for environmental awareness.
The elements included in the invention are as follows:
1.	The use of a catadioptric optical system, and the shortening of the optical path and the easing of separation into wavelengths by obtaining the "intermediate image plane" through placing the first mirror and the second mirror at appropriate positions and angles.
2.	The provision of optical zoom and Multi FoV (Field of View) through the use of a movable lens group.
3.	The ability to obtain multiple wavelengths (Multi Wavelength) by means of a beam splitter cube or a filter positioned rotatably behind the formed intermediate image plane.

Pursuant to Articles 56 and 54 of the European Patent Convention, when the present invention is evaluated by taking into account the prior art obtained as a result of the research conducted, it has been concluded that the 1st and 2nd elements included in the invention disclosure do not contain novelty and an inventive step, and that the 3rd element—when evaluated together with the 1st and 2nd elements—contains novelty but does not contain an inventive step. The final decision will be made by the Intellectual Property Rights Board.
', NULL, NULL, 'Element 1
The use of a catadioptric optical system, and the shortening of the optical path and the easing of separation into wavelengths by obtaining the "intermediate image plane" through placing the first mirror and the second mirror at appropriate positions and angles.
The patent document US5940222A, titled "Catadioptric zoom lens assemblies," dated 1999 and belonging to L3 Technologies Inc., describes catadioptric zoom lens assemblies. A catadioptric zoom lens assembly has a forward-facing primary mirror to form an intermediate image ahead of the primary mirror, and a catoptric objective lens group having a rearward-facing first surface that reflects the secondary mirror located ahead of the primary mirror. A zoom relay lens group is placed optically behind the intermediate image and has a stationary field lens subgroup, a first movable lens subgroup, and a second movable lens subgroup. The G1 catoptric objective lens group has a forward-facing parabolic primary mirror M1 and a hyperbolic rearward-facing secondary mirror M2—that is, a first-surface reflecting mirror placed in front of the primary mirror (M1) to form an intermediate image II in front of the primary mirror (M1).
Element 2
The provision of optical zoom and Multi FoV (Field of View) through the use of a movable lens group.
The patent document US5940222A, titled "Catadioptric zoom lens assemblies," dated 1999 and belonging to L3 Technologies Inc., describes catadioptric zoom lens assemblies. A catadioptric zoom lens assembly has a forward-facing primary mirror to form an intermediate image ahead of the primary mirror, and a catoptric objective lens group having a rearward-facing first surface that reflects the secondary mirror located ahead of the primary mirror. A zoom relay lens group is placed optically behind the intermediate image and has a stationary field lens subgroup, a first movable lens subgroup, and a second movable lens subgroup. The G1 catoptric objective lens group has a forward-facing parabolic primary mirror M1 and a hyperbolic rearward-facing secondary mirror M2—that is, a first-surface reflecting mirror placed in front of the primary mirror (M1) to form an intermediate image II in front of the primary mirror (M1).
Element 3
The ability to obtain multiple wavelengths (Multi Wavelength) by means of a beam splitter cube or a filter positioned rotatably behind the formed intermediate image plane.
The patent document US9857585B2, titled "Rolling beam splitter optical switching mechanism for combination and selection of detector illumination," dated 2018 and belonging to Raytheon Co., describes a rolling beam splitter optical switching mechanism for the combination and selection of beam illumination. The beam splitter cube 38 can be rotated to direct the reflected electromagnetic radiation to either the VIS camera 24 or the NIR camera 26. Figure 3 shows the beam splitter cube 38 oriented to transmit the reflected electromagnetic radiation to the VIS camera 24. Figure 4 shows the beam splitter cube 38 oriented to transmit the reflected electromagnetic radiation to the NIR camera 26. The mirror directs the electromagnetic radiation to an effective focal length (EFL) switching optic (36), which directs the electromagnetic radiation, along the optical path (40), to a beam splitter cube (38) of the embodiments of the present disclosure. The system is configured to direct a customizable percentage of the incoming light (transmitted light) to one device, namely the SWIR camera, and the remaining portion of the incoming light (reflected light) to one of the other two detectors.
When the prior art documents are evaluated, Element 3—when evaluated together with Elements 1 and Element 2—contains novelty but does not contain an inventive step.
', '2026-05-23 16:57:38.712234', '2026-06-03 11:45:51.070801');


--
-- Data for Name: research_report_document; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Name: claim_claim_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.claim_claim_id_seq', 13, true);


--
-- Name: claim_element_claim_element_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.claim_element_claim_element_id_seq', 41, true);


--
-- Name: element_element_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.element_element_id_seq', 270, true);


--
-- Name: invention_disclosure_document_document_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.invention_disclosure_document_document_id_seq', 4, true);


--
-- Name: invention_disclosure_idf_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.invention_disclosure_idf_id_seq', 12, true);


--
-- Name: inventor_qa_document_document_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.inventor_qa_document_document_id_seq', 1, false);


--
-- Name: inventor_qa_qna_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.inventor_qa_qna_id_seq', 12, true);


--
-- Name: patent_patent_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.patent_patent_id_seq', 14, true);


--
-- Name: research_report_document_document_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.research_report_document_document_id_seq', 3, true);


--
-- Name: research_report_research_report_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.research_report_research_report_id_seq', 11, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: app_setting app_setting_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_setting
    ADD CONSTRAINT app_setting_pkey PRIMARY KEY (key);


--
-- Name: claim_element claim_element_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_element
    ADD CONSTRAINT claim_element_pkey PRIMARY KEY (claim_element_id);


--
-- Name: claim claim_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim
    ADD CONSTRAINT claim_pkey PRIMARY KEY (claim_id);


--
-- Name: element element_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.element
    ADD CONSTRAINT element_pkey PRIMARY KEY (element_id);


--
-- Name: invention_disclosure_document invention_disclosure_document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure_document
    ADD CONSTRAINT invention_disclosure_document_pkey PRIMARY KEY (document_id);


--
-- Name: invention_disclosure invention_disclosure_patent_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure
    ADD CONSTRAINT invention_disclosure_patent_id_key UNIQUE (patent_id);


--
-- Name: invention_disclosure invention_disclosure_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure
    ADD CONSTRAINT invention_disclosure_pkey PRIMARY KEY (idf_id);


--
-- Name: inventor_qa_document inventor_qa_document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa_document
    ADD CONSTRAINT inventor_qa_document_pkey PRIMARY KEY (document_id);


--
-- Name: inventor_qa inventor_qa_patent_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa
    ADD CONSTRAINT inventor_qa_patent_id_key UNIQUE (patent_id);


--
-- Name: inventor_qa inventor_qa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa
    ADD CONSTRAINT inventor_qa_pkey PRIMARY KEY (qna_id);


--
-- Name: patent patent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patent
    ADD CONSTRAINT patent_pkey PRIMARY KEY (patent_id);


--
-- Name: research_report_document research_report_document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report_document
    ADD CONSTRAINT research_report_document_pkey PRIMARY KEY (document_id);


--
-- Name: research_report research_report_patent_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report
    ADD CONSTRAINT research_report_patent_id_key UNIQUE (patent_id);


--
-- Name: research_report research_report_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report
    ADD CONSTRAINT research_report_pkey PRIMARY KEY (research_report_id);


--
-- Name: claim_element claim_element_claim_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_element
    ADD CONSTRAINT claim_element_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.claim(claim_id);


--
-- Name: claim_element claim_element_element_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_element
    ADD CONSTRAINT claim_element_element_id_fkey FOREIGN KEY (element_id) REFERENCES public.element(element_id);


--
-- Name: claim claim_patent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim
    ADD CONSTRAINT claim_patent_id_fkey FOREIGN KEY (patent_id) REFERENCES public.patent(patent_id);


--
-- Name: element element_patent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.element
    ADD CONSTRAINT element_patent_id_fkey FOREIGN KEY (patent_id) REFERENCES public.patent(patent_id);


--
-- Name: invention_disclosure_document invention_disclosure_document_idf_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure_document
    ADD CONSTRAINT invention_disclosure_document_idf_id_fkey FOREIGN KEY (idf_id) REFERENCES public.invention_disclosure(idf_id) ON DELETE CASCADE;


--
-- Name: invention_disclosure invention_disclosure_patent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invention_disclosure
    ADD CONSTRAINT invention_disclosure_patent_id_fkey FOREIGN KEY (patent_id) REFERENCES public.patent(patent_id);


--
-- Name: inventor_qa_document inventor_qa_document_qna_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa_document
    ADD CONSTRAINT inventor_qa_document_qna_id_fkey FOREIGN KEY (qna_id) REFERENCES public.inventor_qa(qna_id) ON DELETE CASCADE;


--
-- Name: inventor_qa inventor_qa_patent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventor_qa
    ADD CONSTRAINT inventor_qa_patent_id_fkey FOREIGN KEY (patent_id) REFERENCES public.patent(patent_id);


--
-- Name: research_report_document research_report_document_research_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report_document
    ADD CONSTRAINT research_report_document_research_report_id_fkey FOREIGN KEY (research_report_id) REFERENCES public.research_report(research_report_id) ON DELETE CASCADE;


--
-- Name: research_report research_report_patent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_report
    ADD CONSTRAINT research_report_patent_id_fkey FOREIGN KEY (patent_id) REFERENCES public.patent(patent_id);


--
-- PostgreSQL database dump complete
--

\unrestrict 3bcnw4Mwtw93dRkgTZ12tv2e1L5ymCtjNFe0VaKDayYAc1RobIevX8sdL3foChp

