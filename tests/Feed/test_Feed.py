import allure
import pytest

from src.actions import Feed_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_001_checkViewPosts")
@allure.description("Feed: El muro muestra sus publicaciones y la de otro autor con su nombre")
def test_00_09_001_checkViewPosts(page):
    assert_action(actions.test_00_09_001_checkViewPosts, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_002_checkTextOnlyPost")
@allure.description("Feed: Publicar solo texto; 'Publicar' se deshabilita con el texto vacío")
def test_00_09_002_checkTextOnlyPost(page):
    assert_action(actions.test_00_09_002_checkTextOnlyPost, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_003_checkImageFromFile")
@allure.description("Feed: Publicar con una imagen subida desde archivo")
def test_00_09_003_checkImageFromFile(page):
    assert_action(actions.test_00_09_003_checkImageFromFile, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_004_checkImageByUrl")
@allure.description("Feed: Publicar con una imagen por URL")
def test_00_09_004_checkImageByUrl(page):
    assert_action(actions.test_00_09_004_checkImageByUrl, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_005_checkInvalidFileRejected")
@allure.description("Feed: Un archivo no soportado o de más de 5 MB se rechaza en el cliente")
def test_00_09_005_checkInvalidFileRejected(page):
    assert_action(actions.test_00_09_005_checkInvalidFileRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_006_checkRemoveImageBeforePosting")
@allure.description("Feed: Quitar la imagen seleccionada antes de publicar")
def test_00_09_006_checkRemoveImageBeforePosting(page):
    assert_action(actions.test_00_09_006_checkRemoveImageBeforePosting, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_007_checkEditOwnPost", depends=["test_00_09_002_checkTextOnlyPost"])
@allure.description("Feed: Editar una publicación propia muestra el nuevo texto y '(Editado)'")
def test_00_09_007_checkEditOwnPost(page):
    assert_action(actions.test_00_09_007_checkEditOwnPost, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_008_checkDeleteOwnPost")
@allure.description("Feed: Eliminar una publicación propia la quita del muro y de la API")
def test_00_09_008_checkDeleteOwnPost(page):
    assert_action(actions.test_00_09_008_checkDeleteOwnPost, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_009_checkNoEditOnOthersPosts", depends=["test_00_09_001_checkViewPosts"])
@allure.description("Feed: En publicaciones de otros no aparecen 'Editar' ni 'Eliminar'")
def test_00_09_009_checkNoEditOnOthersPosts(page):
    assert_action(actions.test_00_09_009_checkNoEditOnOthersPosts, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_010_checkCannotEditOthersPost")
@allure.description("Feed: Otro usuario (no admin) recibe 403 al editar o borrar un post de S y el post no cambia")
def test_00_09_010_checkCannotEditOthersPost(page):
    assert_action(actions.test_00_09_010_checkCannotEditOthersPost, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_09_011_checkLikePersistsOnReload")
@allure.description("Feed: Dar y quitar like actualiza el botón y el contador, y ambos se mantienen al recargar")
def test_00_09_011_checkLikePersistsOnReload(page):
    assert_action(actions.test_00_09_011_checkLikePersistsOnReload, page)
