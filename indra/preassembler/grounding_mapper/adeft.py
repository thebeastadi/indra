import logging
from .mapper import GroundingMapper

logger = logging.getLogger(__name__)

# If the adeft disambiguator is installed, load adeft models to
# disambiguate acronyms and shortforms
try:
    from adeft import available_shortforms as available_adeft_models
    from adeft.disambiguate import load_disambiguator
    adeft_disambiguators = {}
    for shortform in available_adeft_models:
        adeft_disambiguators[shortform] = load_disambiguator(shortform)
except Exception:
    logger.info('Adeft will not be available for grounding disambiguation.')
    adeft_disambiguators = {}


def run_adeft_disambiguation(stmt, agent, idx):
    """Run Adeft disambiguation on an Agent in a given Statement.

    This function looks at the evidence of the given Statement and attempts
    to look up the full paper or the abstract for the evidence. If both of
    those fail, the evidence sentence itself is used for disambiguation.
    The disambiguation model corresponding to the Agent text is then called,
    and the highest scoring returned grounding is set as the Agent's new
    grounding.

    The Statement's annotations as well as the Agent are modified in place
    and no value is returned.

    Parameters
    ----------
    stmt : indra.statements.Statement
        An INDRA Statement in which the Agent to be disambiguated appears.
    agent : indra.statements.Agent
        The Agent (potentially grounding mapped) which we want to
        disambiguate in the context of the evidence of the given Statement.
    idx : int
        The index of the new Agent's position in the Statement's agent list
        (needed to set annotations correctly).
    """
    # If the Statement doesn't have evidence for some reason, then there is
    # no text to disambiguate by
    # NOTE: we might want to try disambiguating by other agents in the
    # Statement
    if not stmt.evidence:
        return
    # Initialize annotations if needed so Adeft predicted
    # probabilities can be added to Agent annotations
    annots = stmt.evidence[0].annotations
    agent_txt = agent.db_refs['TEXT']
    if 'agents' in annots:
        if 'adeft' not in annots['agents']:
            annots['agents']['adeft'] = \
                {'adeft': [None for _ in stmt.agent_list()]}
    else:
        annots['agents'] = {'adeft': [None for _ in stmt.agent_list()]}
    grounding_text = _get_text_for_grounding(stmt, agent_txt)
    if grounding_text:
        res = adeft_disambiguators[agent_txt].disambiguate(
            [grounding_text])
        ns_and_id, standard_name, disamb_scores = res[0]
        # If the highest score is ungrounded we explicitly remove grounding
        # and reset the (potentially incorrectly standardized) name to the
        # original text value.
        if ns_and_id == 'ungrounded':
            agent.name = agent_txt
            agent.db_refs = {'TEXT': agent_txt}
        # Otherwise we update the db_refs with what we got from DEFT
        # and set the standard name
        else:
            db_ns, db_id = ns_and_id.split(':', maxsplit=1)
            agent.db_refs = {'TEXT': agent_txt, db_ns: db_id}
            agent.name = standard_name
            logger.info('Disambiguated %s to: %s, %s:%s' %
                        (agent_txt, standard_name, db_ns, db_id))
            GroundingMapper.standardize_agent_name(agent,
                                                   standardize_refs=True)
            annots['agents']['adeft'][idx] = disamb_scores


def _get_text_for_grounding(stmt, agent_text):
    """Get text context for Adeft disambiguation

    If the INDRA database is available, attempts to get the fulltext from
    which the statement was extracted. If the fulltext is not available, the
    abstract is returned. If the indra database is not available, uses the
    pubmed client to get the abstract. If no abstract can be found, falls back
    on returning the evidence text for the statement.

    Parameters
    ----------
    stmt : py:class:`indra.statements.Statement`
        Statement with agent we seek to disambiguate.

    agent_text : str
       Agent text that needs to be disambiguated

    Returns
    -------
    text : str
        Text for Adeft disambiguation
    """
    text = None
    # First we will try to get content from the DB
    try:
        from indra_db.util.content_scripts \
            import get_text_content_from_text_refs
        from indra.literature.adeft_tools import universal_extract_text
        refs = stmt.evidence[0].text_refs
        # Prioritize the pmid attribute if given
        if stmt.evidence[0].pmid:
            refs['PMID'] = stmt.evidence[0].pmid
        logger.info('Obtaining text for disambiguation with refs: %s' %
                    refs)
        content = get_text_content_from_text_refs(refs)
        text = universal_extract_text(content, contains=agent_text)
        if text:
            return text
    except Exception as e:
        logger.info('Could not get text for disambiguation from DB.')
    # If that doesn't work, we try PubMed next
    if text is None:
        from indra.literature import pubmed_client
        pmid = stmt.evidence[0].pmid
        if pmid:
            logger.info('Obtaining abstract for disambiguation for PMID%s' %
                        pmid)
            text = pubmed_client.get_abstract(pmid)
            if text:
                return text
    # Finally, falling back on the evidence sentence
    if text is None:
        logger.info('Falling back on sentence-based disambiguation')
        text = stmt.evidence[0].text
        return text
    return None
