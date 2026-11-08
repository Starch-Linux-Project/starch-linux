// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the built plugin, not a second implementation of its selection rules.
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "utils/PluginFactory.h"
#include "viewpages/ViewStep.h"
#include <QApplication>
#include <QCheckBox>
#include <QPluginLoader>
#include <QWidget>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv)
{
    QApplication app(argc, argv);
    Calamares::JobQueue queue;
    QPluginLoader loader("/usr/lib/calamares/modules/starchadvanced/libcalamares_viewmodule_starchadvanced.so");
    auto* factory = qobject_cast<CalamaresPluginFactory*>(loader.instance());
    if (!factory) throw std::runtime_error(loader.errorString().toStdString());
    auto* step = factory->create<Calamares::ViewStep>();
    if (!step) throw std::runtime_error("Could not create Advanced page");
    step->setConfigurationMap({{"liteEnabled", true}});
    auto* page = step->widget();
    auto* ack = page->findChild<QCheckBox*>("advancedAcknowledgement");
    auto* lite = page->findChild<QCheckBox*>("starchLite");
    auto* xfce = page->findChild<QCheckBox*>("starchLiteXfce");
    auto* cosmic = page->findChild<QCheckBox*>("starchCosmic");
    if (!ack || !lite || !xfce || !cosmic) throw std::runtime_error("Missing checkbox");
    auto check = [&](const char* desktop, bool expectedLite) {
        auto* gs = queue.globalStorage();
        if (gs->value("starchDesktop").toString() != desktop
            || gs->value("starchLite").toBool() != expectedLite
            || gs->value("starchLiteXfce").toBool() != (QString(desktop) == "xfce")
            || (xfce->isChecked() && cosmic->isChecked()))
            throw std::runtime_error("Incorrect or contradictory desktop selection");
    };
    check("plasma", false);
    ack->setChecked(true);
    cosmic->setChecked(true);
    check("cosmic", false);
    lite->setChecked(true);
    check("cosmic", true);
    xfce->setChecked(true);
    check("xfce", true);
    cosmic->setChecked(true);
    check("cosmic", true);
    cosmic->setChecked(false);
    check("plasma", true);
    xfce->setChecked(true);
    lite->setChecked(false);
    check("plasma", false);
    cosmic->setChecked(true);
    ack->setChecked(false);
    check("plasma", false);
    delete step;
    std::cout << "Advanced plugin checkbox transitions passed.\n";
}
