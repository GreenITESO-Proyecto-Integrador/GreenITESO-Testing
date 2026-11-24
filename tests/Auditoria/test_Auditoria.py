import allure
import pytest

from src.actions import Auditoria_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_000_checkSetUp")
@allure.description("Auditoría: Setup, crea con la API las evidencias pendientes y las propuestas de prueba")
def test_00_07_000_checkSetUp(page):
    assert_action(actions.test_00_07_000_checkSetUp, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_001_checkOpenAuditPanel")
@allure.description("Auditoría: El admin abre /audit y ve el panel con sus dos pestañas y la cola cargada")
def test_00_07_001_checkOpenAuditPanel(page):
    assert_action(actions.test_00_07_001_checkOpenAuditPanel, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_002_checkPendingEvidenceList", depends=["test_00_07_000_checkSetUp"])
@allure.description("Auditoría: La cola lista la evidencia pendiente con acción, estado, puntos, usuario y su foto")
def test_00_07_002_checkPendingEvidenceList(page):
    assert_action(actions.test_00_07_002_checkPendingEvidenceList, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_003_checkApproveEvidence", depends=["test_00_07_000_checkSetUp"])
@allure.description(
    "Auditoría: Aprobar una evidencia la quita de la cola, la deja APPROVED y suma los puntos al usuario"
)
def test_00_07_003_checkApproveEvidence(page):
    assert_action(actions.test_00_07_003_checkApproveEvidence, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_004_checkRejectNeedsReason", depends=["test_00_07_000_checkSetUp"])
@allure.description(
    "Auditoría: Rechazar pide el motivo (vacío o solo espacios no manda nada) y con motivo guarda REJECTED"
)
def test_00_07_004_checkRejectNeedsReason(page):
    assert_action(actions.test_00_07_004_checkRejectNeedsReason, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_005_checkApproveProposal", depends=["test_00_07_000_checkSetUp"])
@allure.description(
    "Auditoría: Aprobar una propuesta muestra el aviso y manda el POST (simulado fuera del stack desechable)"
)
def test_00_07_005_checkApproveProposal(page):
    assert_action(actions.test_00_07_005_checkApproveProposal, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_006_checkRejectProposalWithReason", depends=["test_00_07_000_checkSetUp"])
@allure.description(
    "Auditoría: Rechazar una propuesta exige motivo, la deja REJECTED y el motivo se ve en 'Rechazadas'"
)
def test_00_07_006_checkRejectProposalWithReason(page):
    assert_action(actions.test_00_07_006_checkRejectProposalWithReason, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_007_checkProposalsTabFromUrl")
@allure.description(
    "Auditoría: ?tab=propuestas abre Propuestas, la pestaña actualiza la URL y una desconocida cae en Evidencias"
)
def test_00_07_007_checkProposalsTabFromUrl(page):
    assert_action(actions.test_00_07_007_checkProposalsTabFromUrl, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_07_008_checkEmptyAndErrorStates")
@allure.description("Auditoría: Estados vacíos y de error de la cola y de las propuestas, y Reintentar los recupera")
def test_00_07_008_checkEmptyAndErrorStates(page):
    assert_action(actions.test_00_07_008_checkEmptyAndErrorStates, page)
