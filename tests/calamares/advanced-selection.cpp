// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the built plugin, not a second implementation of its selection rules.
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QApplication>
#include <QRadioButton>
#include <QPluginLoader>
#include <QWidget>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv)
{
    QApplication app(argc, argv);
    Calamares::JobQueue queue;
    QPluginLoader loader(argc > 1 ? argv[1] : "/usr/lib/calamares/modules/starchadvanced/libcalamares_viewmodule_starchadvanced.so");
    auto* factory = qobject_cast<CalamaresPluginFactory*>(loader.instance());
    if (!factory) throw std::runtime_error(loader.errorString().toStdString());
    auto* step = factory->create<Calamares::ViewStep>();
    if (!step) throw std::runtime_error("Could not create Installation Profiles page");
    step->setConfigurationMap({{"liteEnabled", true}});
    auto* page = step->widget();
    auto* plasma = page->findChild<QRadioButton*>("starchPlasma");
    auto* lite = page->findChild<QRadioButton*>("starchLite");
    auto* cosmic = page->findChild<QRadioButton*>("starchCosmic");
    if (!plasma || !lite || !cosmic || page->findChildren<QRadioButton*>().size() != 3)
        throw std::runtime_error("Expected exactly three profiles");
    auto check = [&](const char* desktop, bool expectedLite) {
        auto* gs = queue.globalStorage();
        if (gs->value("starchDesktop").toString() != desktop
            || gs->value("starchLite").toBool() != expectedLite
            || gs->value("starchLiteXfce").toBool() != expectedLite
            || int(plasma->isChecked()) + int(lite->isChecked()) + int(cosmic->isChecked()) != 1)
            throw std::runtime_error("Incorrect or contradictory profile selection");
        page->hide();
        if (step->widget() != page) throw std::runtime_error("Page recreated on navigation");
        page->show();
        if (gs->value("starchDesktop").toString() != desktop)
            throw std::runtime_error("Navigation lost selection");
    };
    if (step->prettyName() != "Installation Profiles" || !plasma->isChecked())
        throw std::runtime_error("Incorrect title or default");
    check("plasma", false);
    // Exercise every pair of transitions, including clicking the selected radio.
    for (auto* from : {plasma, cosmic, lite}) {
        from->click();
        for (auto* to : {plasma, cosmic, lite}) {
            from->click();
            to->click();
            to->click();
            check(to == lite ? "xfce" : (to == cosmic ? "cosmic" : "plasma"), to == lite);
        }
    }
    lite->click();
    step->setConfigurationMap({{"liteEnabled", false}});
    check("plasma", false);
    lite->click();
    check("plasma", false);
    cosmic->click();
    check("cosmic", false);
    delete step;
    std::cout << "Installation Profiles radio transitions passed.\n";
}
